"""QA stand-in. Patched SDK transport, no network and no production settings."""
import json
from pathlib import Path
from unittest.mock import patch


def ref_for(excerpts, prefix):
    return next(row['id'] for row in excerpts if row['text'].startswith(prefix))


def mock_provider(directory):
    counts = directory/'fixture-provider.json'
    counts.write_text(json.dumps([]),encoding='utf-8')

    class Fake:
        def __init__(self, **kwargs):
            from django.conf import settings
            assert settings.ESEPTEP_DEMO_MODE and settings.OPENAI_API_KEY == 'mock-only'
            assert kwargs['max_retries'] == 0
            self.responses = self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def create(self, **payload):
            op = payload['text']['format']['name']
            attempts = json.loads(counts.read_text(encoding='utf-8'))
            attempts.append(op)
            counts.write_text(json.dumps(attempts),encoding='utf-8')
            if op == 'classified_plan_rooms':
                result = {'document_kind':'floor_plan','floor_pages':[1],
                          'rooms':[dict(name=n, area=a, kind=k, source='stated',page=1,page_type='floor_plan',
                                        evidence=f'{n} {a:.2f} м²',schedule_evidence='',finish=None)
                                   for n,a,k in [('Гостиная',20,'other'),('Холл',6,'other'),
                                                  ('Спальня',10.08,'other'),('Санузел',3.92,'bathroom')]]}
            elif op == 'contract_shorten':
                source=json.loads(payload['input'])['source']
                pref=lambda *values:[ref_for(source,value) for value in values]
                result={'sections':[
                    {'key':'scope','text':'Ламинат учебной серии L, 12 упаковок. Замены согласуются отдельно.', 'refs':pref('1.2.')},
                    {'key':'price','text':'Товары стоят 12 000 ₸: 12 × 1 000 ₸; доставка в сумму не включена. 30% (3 600 ₸) до 2 декабря 2026 года. 70% (8 400 ₸) после полной приёмки, но не позже 10 декабря 2026 года; если полная приёмка не состоялась, срок согласовать отдельно.', 'refs':pref('2.1.','2.2.','2.3.')},
                    {'key':'dates','text':'Срок поставки: 8 декабря 2026 года, 10:00–13:00 по Шымкенту.', 'refs':pref('3.1.')},
                    {'key':'delivery','text':'Одна партия: 12 упаковок 8 декабря 2026 года, 10:00–13:00, время Шымкента. Покупатель оплачивает перевозчика отдельно, тариф и адрес нужно уточнить.', 'refs':pref('3.1.','3.2.')},
                    {'key':'acceptance','text':'Зафиксировать переданные, отсутствующие и повреждённые упаковки раздельно по Приложению 2.', 'refs':pref('4.1.','4.2.')},
                    {'key':'defects','text':'Согласовать срок устранения подтверждённых недостатков: пункты 5.2 и 7.2 оригинала противоречат друг другу (3 и 5 рабочих дней).', 'refs':pref('5.2.','7.2.')},
                    {'key':'exclusions','text':'Не включены укладка, подготовка основания, демонтаж, подъём, вынос упаковки, монтаж плинтуса.', 'refs':pref('1.3.')},
                    {'key':'appendices','text':'Приложение 1 — спецификация. Приложение 2 — форма приёмки.', 'refs':pref('Приложение 1','Приложение 2')},
                ],'changes':[
                    {'kind':'conflict','text':'Пункты 5.2 и 7.2: 3 против 5 рабочих дней со дня подтверждения замечания. Не выбирать без согласования.', 'refs':pref('5.2.','7.2.')},
                    {'kind':'merged','text':'Цена и график оплаты объединены.', 'refs':pref('2.1.','2.2.','2.3.')},
                ]}
            elif op == 'contract_amend':
                result={'text':'Две партии по 6 упаковок: 5 и 8 декабря 2026 года, 10:00–13:00, время Шымкента. Всего 12 упаковок. Покупатель оплачивает перевозчика отдельно, тариф и адрес нужно уточнить.',
                        'explanation':'Одна партия заменена двумя; срок завершения и плательщик не изменились.'}
            else:
                raise AssertionError('Unexpected provider operation in fixture')
            class Response:
                def model_dump(self,**kwargs):
                    return {
                        'id':f'resp_fixture_{len(attempts)}','model':'gpt-6.1-sol','service_tier':'default',
                        'status':'completed','usage':{'input_tokens':3000,'output_tokens':800,'total_tokens':3800},
                        'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(result,ensure_ascii=False)}]}],
                    }
            return Response()

    return patch('core.openai_client.OpenAI', Fake).start()
