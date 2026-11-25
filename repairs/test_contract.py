import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader, PdfWriter

from core.local_ai_budget import initialize, reserve, status
from .models import ContractAIRequest, ContractSource, DemoContract, PilotCity
from .tests import RepairFlowTests

FIXTURE = Path(__file__).with_name('fixtures') / 'ESEPTEP_original_DEMO-01.docx'


@override_settings(CONTRACT_DEMO_ENABLED=True, CONTRACT_AI_ENABLED=True, OPENAI_API_KEY='mock-only',
                   OPENAI_LIVE_CONFIRMED=True, OPENAI_MODEL='gpt-6.1-sol', OPENAI_MAX_OUTPUT_TOKENS=1800)
class DemoContractTests(TestCase):
    setUpTestData = classmethod(RepairFlowTests.setUpTestData.__func__)
    user_for = staticmethod(RepairFlowTests.user_for)
    browser = RepairFlowTests.browser
    url = RepairFlowTests.url
    post = RepairFlowTests.post
    accept = RepairFlowTests.accept

    def setUp(self):
        self.setup = TemporaryDirectory()
        self.addCleanup(self.setup.cleanup)
        self.ledger = Path(self.setup.name) / 'test-budget.sqlite3'
        initialize(self.ledger, 16, {'synthetic_only': True})
        settings = override_settings(LOCAL_AI_BUDGET_PATH=str(self.ledger))
        settings.enable()
        self.addCleanup(settings.disable)
        self.accept('materials')
        self.owner = self.browser(self.buyer)

    def path(self, name='contract_show', *extra, kind='materials'):
        return reverse(f'repairs:{name}', args=[self.project.pk,*([kind] if name!='contract_choose' else []),*extra])

    def action(self, op, **kwargs):
        return self.owner.post(self.path('contract_action'), {'action':op,**kwargs})

    def create(self, language='ru'):
        self.assertEqual(self.action('create', language=language, style='source').status_code,302)
        return DemoContract.objects.get()

    def upload(self, name='original.docx'):
        return self.action('upload', source=SimpleUploadedFile(name, FIXTURE.read_bytes()))

    @staticmethod
    def response(output, seq=1):
        return {'id':f'resp_test_{seq}', 'model':'gpt-6.1-sol', 'service_tier':'default','status':'completed',
                'usage':{'input_tokens':3000,'output_tokens':800,'total_tokens':3800},
                'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(output,ensure_ascii=False)}]}]}

    @staticmethod
    def summarize(source):
        ref = lambda phrase:next(item['id'] for item in source.excerpts if phrase in item['text'])
        return {
            'sections':[
                {'key':'price','text':'12 000 ₸. 30% — 3 600 ₸ к 02.12.2026; 70% — 8 400 ₸ после полной приёмки, до 10.12.2026.',
                 'refs':[ref('3 600')]},
                {'key':'delivery','text':'Одна партия 12 упаковок 08.12.2026 10:00–13:00. Покупатель оплачивает перевозчика отдельно.',
                 'refs':[ref('8 декабря 2026')]},
                {'key':'defects','text':'Срок устранения подтверждённых недостатков требует согласования.',
                 'refs':[ref('5.2'),ref('7.2')]},
                {'key':'appendices','text':'Приложение 1 — спецификация. Приложение 2 — форма приёмки.',
                 'refs':[ref('Приложение 1'),ref('Приложение 2')]},
            ],
            'changes':[{'kind':'conflict','text':'Пункты 5.2 и 7.2 дают 3 и 5 рабочих дней. Нужно решение.',
                        'refs':[ref('5.2'),ref('7.2')]}],
        }

    @patch('core.openai_client.OpenAI')
    def test_contract_chain_from_source_keeps_terms_and_spends_once_per_operation(self, sdk):
        contract=self.create()
        self.assertEqual(self.upload().status_code,302)
        src=ContractSource.objects.get()
        self.assertEqual(self.upload('identical-renamed.docx').status_code,302)
        self.assertEqual(ContractSource.objects.count(),1)
        provider=sdk.return_value.__enter__.return_value.responses.create
        amended='Покупатель оплачивает перевозчика отдельно. Две партии по 6 упаковок: 05.12.2026 и 08.12.2026 10:00–13:00.'
        provider.side_effect=[
            FakeResponse(self.response(self.summarize(src))),
            FakeResponse(self.response({'text':amended,'explanation':'Заменена одна поставка двумя партиями.'}, 2)),
        ]
        reply=self.action('shorten', source=src.pk,revision=1)
        self.assertEqual(reply.status_code,302)
        self.assertEqual(self.action('shorten',source=src.pk,revision=1)['Location'],reply['Location'])
        self.assertContains(self.owner.get(reply['Location']), 'Пункты 5.2 и 7.2')
        self.assertEqual(provider.call_count,1)
        self.assertEqual(status(self.ledger)['accounted_cents'],219)
        self.assertEqual(self.action('apply',proposal=ContractAIRequest.objects.get(operation='shorten').pk).status_code,302)
        self.assertEqual(self.action('manual',revision=2,date='2026-11-30').status_code,302)
        self.assertEqual(provider.call_count,1)
        request=dict(revision=3,section='delivery',instruction='Предусмотри доставку двумя партиями по шесть, 5 и 8 декабря 2026 года.')
        suggested=self.action('amend', **request)
        self.assertContains(self.owner.get(suggested['Location']), amended)
        page=self.owner.get(self.path())
        self.assertContains(page, 'Одна партия 12 упаковок')
        self.assertNotContains(page, amended)
        prop=ContractAIRequest.objects.get(operation='amend')
        self.assertTrue(0 < len(json.loads(provider.call_args.kwargs['input'])['related']) < 5)
        self.assertNotIn('source', json.loads(provider.call_args.kwargs['input']))
        self.assertEqual(self.action('apply',proposal=prop.pk).status_code,302)
        self.assertEqual(self.action('apply',proposal=prop.pk).status_code,302)
        self.assertEqual(self.action('amend',**request)['Location'],suggested['Location'])
        self.assertEqual(self.action('shorten',source=src.pk,revision=4)['Location'],reply['Location'])
        self.assertEqual(provider.call_count,2)
        self.assertEqual(status(self.ledger)['accounted_cents'],222)
        contract.refresh_from_db()
        self.assertEqual(contract.current_revision,4)
        streamed=self.owner.get(self.path('contract_download',4,'docx'))
        with ZipFile(io.BytesIO(streamed.content)) as z:
            doc=z.read('word/document.xml').decode()
        pdf=PdfReader(io.BytesIO(self.owner.get(self.path('contract_download',4,'pdf')).content))
        pdf_text=' '.join(' '.join(p.extract_text().split()) for p in pdf.pages)
        for output in (doc,pdf_text):
            for needle in ('12000.00 ₸','2026-11-30','10.12.2026','Покупатель оплачивает перевозчика отдельно','05.12.2026','7.2'):
                self.assertIn(needle,output)
        self.assertEqual(self.owner.get(self.path('contract_original',src.pk)).content,FIXTURE.read_bytes())
        self.assertEqual(self.owner.get(self.path('contract_original',src.pk))['Cache-Control'],'private, no-store')
        self.assertContains(self.owner.get(self.path()+'?version=4&compare=3'),'Было')
        self.assertContains(self.owner.get(self.path('contract_choose')),'Открыть договор')

    @patch('core.openai_client.OpenAI')
    def test_scan_rejected_before_provider_and_spending_limit_cannot_disable_manual_use(self, sdk):
        self.create()
        out=io.BytesIO()
        writer=PdfWriter(); writer.add_blank_page(width=400,height=500); writer.write(out)
        scan=self.action('upload', source=SimpleUploadedFile('scan.pdf',out.getvalue()))
        self.assertContains(scan,'Вызова ИИ не было',status_code=400)
        self.assertFalse(ContractSource.objects.exists())
        self.upload()
        reserve(self.ledger, {'model':'gpt-6.1-sol','max_output_tokens':1800,'service_tier':'default','input':'plan with an unresolved reservation'})
        result=self.action('shorten',source=ContractSource.objects.get().pk,revision=1)
        self.assertContains(result,'Лимита пилота',status_code=400)
        self.assertFalse(ContractAIRequest.objects.exists())
        self.assertEqual(self.action('manual',revision=1,date='2026-12-01').status_code,302)
        self.assertEqual(self.owner.get(self.path('contract_download',2,'docx')).status_code,200)
        sdk.assert_not_called()

    @patch('core.openai_client.OpenAI')
    def test_private_gate_controls_screen_post_and_all_downloads(self,sdk):
        self.create()
        self.upload()
        routes=[self.path(),self.path('contract_choose'),self.path('contract_download',1,'pdf'),
                self.path('contract_original',ContractSource.objects.get().pk)]
        for user in (self.stranger,self.shop,self.master,self.reviewer):
            c=self.browser(user)
            for route in routes:
                self.assertEqual(c.get(route).status_code,404)
            self.assertEqual(c.post(self.path('contract_action'),{'action':'amend'}).status_code,404)
        with override_settings(CONTRACT_DEMO_ENABLED=False):
            self.assertEqual(self.owner.get(self.path()).status_code,404)
        PilotCity.objects.update(enabled=False)
        for route in routes:
            self.assertEqual(self.owner.get(route).status_code,404)
        sdk.assert_not_called()

    @patch('core.openai_client.OpenAI')
    def test_incomplete_provider_reason_is_safe_persisted_and_does_not_retry_or_reconcile(self, sdk):
        self.create()
        self.upload()
        src = ContractSource.objects.get()
        provider = sdk.return_value.__enter__.return_value.responses.create
        rsp = self.response({})
        rsp.update(status='incomplete', incomplete_details={'reason':'max_output_tokens'}, output=[
            {'type':'message','content':[{'type':'output_text','text':'private partial output not rendered'}]}])
        provider.return_value = FakeResponse(rsp)
        req = self.action('shorten', source=src.pk, revision=1)
        record = ContractAIRequest.objects.get()
        self.assertEqual(record.status,'failed')
        self.assertEqual(record.result['error'],'provider_output_limit')
        self.assertEqual(record.result['usage']['provider_status'],'incomplete')
        self.assertEqual(record.result['usage']['incomplete_reason'],'max_output_tokens')
        self.assertEqual(record.result['usage']['tokens']['output_tokens'],800)
        self.assertNotIn('private partial',str(record.result))
        self.assertContains(self.owner.get(req['Location']),'ИИ не успел закончить ответ')
        self.assertEqual(self.action('shorten',source=src.pk,revision=1)['Location'],req['Location'])
        self.assertEqual(provider.call_count,1)
        self.assertEqual(status(self.ledger)['accounted_cents'],816)
        self.assertEqual(status(self.ledger)['open_holds'],1)
        self.assertEqual(DemoContract.objects.get().current_revision,1)
        self.assertEqual(self.action('manual',revision=1,date='2026-11-30').status_code,302)
        self.assertEqual(self.owner.get(self.path('contract_download',2,'pdf')).status_code,200)

    def test_works_from_price_stays_unknown_and_document_language_is_independent(self):
        self.accept('works')
        path=self.path('contract_action',kind='works')
        self.assertEqual(self.owner.post(path,{'action':'create','language':'kk','style':'template'}).status_code,302)
        self.assertEqual(DemoContract.objects.get().confirmed_snapshot['total'],'')
        for ui, label in (('ru','Предложить правку'),('kk','Түзету ұсыну')):
            self.owner.cookies['django_language']=ui
            page=self.owner.get(self.path(kind='works'))
            self.assertContains(page,label)
            self.assertContains(page,'Нақтылау қажет')
            self.assertContains(page,'Жөндеу жұмыстары')
            self.assertNotContains(page,'80000')


class FakeResponse:
    def __init__(self,data):
        self.data=data

    def model_dump(self, **kwargs):
        return self.data
