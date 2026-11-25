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


    @patch('core.openai_client.OpenAI')
    def test_two_orders_are_versioned_and_export_without_ai(self, provider):
        from accounts.models import ClientProject, ServiceRequest, WholeSupplierOffer
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from .models import Agreement, ContractTemplateVersion, Repair, Terms
        from .contract_copy import CLAUSES

        existing = Agreement.objects.get()
        buyer2 = self.stranger
        buyer2.first_name = 'Айгуль'
        buyer2.save(update_fields=['first_name'])
        project2 = ClientProject.objects.create(user=buyer2, title='Независимый заказ', city='Шымкент', area_m2=40, rooms=2)
        repair2 = Repair.objects.create(project=project2, city=self.city, enabled=True)
        req = ServiceRequest.objects.create(client=buyer2, project=project2, target_supplier=self.supplier,
                                           request_type='supplier', status='accepted')
        offer = WholeSupplierOffer.objects.create(request=req, supplier=self.supplier, snapshot=self.supplier_offer.snapshot)
        agreement2 = Agreement.objects.create(repair=repair2, request=req, supplier_offer=offer,
                                             partner=self.shop, kind='materials', provider=existing.provider,
                                             original_offer=existing.original_offer)
        term = existing.versions.get()
        Terms.objects.create(agreement=agreement2, revision=1, total=term.total, lines=term.lines,
                             proposed_by=self.shop, accepted_by=buyer2, accepted_at=timezone.now())
        buyer2_client = self.browser(buyer2)
        p2 = lambda name='contract_show', *extra: reverse('repairs:'+name, args=[project2.pk, 'materials', *extra])
        self.assertEqual(self.action('create',style='template',language='ru').status_code,302)
        self.assertEqual(buyer2_client.post(p2('contract_action'),{'action':'create','style':'template','language':'ru'}).status_code,302)
        d1 = DemoContract.objects.get(agreement=existing)
        d2 = DemoContract.objects.get(agreement=agreement2)
        self.assertEqual(d1.template_version_id,d2.template_version_id)
        self.assertEqual(d1.template_version.revision,1)
        self.assertContains(self.owner.get(self.path()), 'стоимость доставки.')
        self.assertContains(self.owner.get(self.path()), '12 упак. × 1000.00 ₸')
        changed = 'Две партии по 6 упаковок: 05.12.2026 и 08.12.2026.'
        self.assertEqual(self.action('manual',revision=1,date='2026-11-30',clause_delivery=changed).status_code,302)
        compare = self.owner.get(self.path()+'?version=2&compare=1')
        self.assertContains(compare,'Было')
        self.assertContains(compare,changed)
        self.assertNotContains(buyer2_client.get(p2()),changed)
        self.assertEqual(buyer2_client.get(self.path()).status_code,404)

        def outputs(browser, url):
            with ZipFile(io.BytesIO(browser.get(url('docx')).content)) as f:
                doc = f.read('word/document.xml').decode()
            pdf = PdfReader(io.BytesIO(browser.get(url('pdf')).content))
            pdf_text = ' '.join(' '.join(page.extract_text().split()) for page in pdf.pages)
            return doc,pdf_text
        for value in outputs(self.owner,lambda ext:self.path('contract_download',2,ext)):
            self.assertIn(changed,value)
            self.assertIn('2026-11-30',value)
        for value in outputs(buyer2_client,lambda ext:p2('contract_download',1,ext)):
            self.assertNotIn(changed,value)
            self.assertNotIn('2026-11-30',value)
            self.assertIn('Айгуль',value)
        library = reverse('repairs:contract_library')
        self.assertEqual(self.owner.get(library).status_code,404)
        operator = get_user_model().objects.create_superuser(username='template-owner')
        staff = self.browser(operator)
        sections = {row['key']:row['text'] for row in d1.template_version.sections}
        self.assertEqual(set(sections),set(CLAUSES))
        new_scope = 'Новая редакция общего шаблона только для будущих заказов.'
        self.assertEqual(staff.post(library,{'action':'save','revision':1,**sections,'scope':new_scope}).status_code,302)
        self.assertContains(staff.get(library),new_scope)
        self.assertEqual(ContractTemplateVersion.objects.filter(kind='materials',language='ru').count(),2)
        self.assertNotContains(self.owner.get(self.path()),new_scope)
        self.assertNotContains(buyer2_client.get(p2()),new_scope)
        self.assertEqual(ContractTemplateVersion.objects.filter(revision=1).count(),4)
        self.assertEqual(ContractAIRequest.objects.count(),0)
        provider.assert_not_called()


    @patch('core.openai_client.OpenAI')
    def test_uploaded_full_basis_edit_compare_and_download_retains_original(self, sdk):
        contract = self.create()
        self.assertEqual(self.upload().status_code,302)
        src = ContractSource.objects.get()
        basis = self.action('use_source',source=src.pk,revision=1)
        self.assertEqual(basis.status_code,302)
        self.assertEqual(self.action('use_source',source=src.pk,revision=1).status_code,302)
        self.assertContains(self.owner.get(basis['Location']),src.excerpts[-1]['text'][:60])
        before = src.excerpts[0]['text']
        changed = 'Синтетическая правка первого пункта, остальные условия сохранены.'
        self.assertContains(self.owner.get(self.path()+'?source_edit=p1'),before)
        self.assertEqual(self.action('source_patch',revision=2,section='p1',text=changed).status_code,302)
        current = self.owner.get(self.path()+'?version=3&compare=2')
        self.assertContains(current,'Было')
        self.assertContains(current,changed)
        self.assertContains(current,before)
        self.assertEqual(self.owner.get(self.path('contract_original',src.pk)).content,FIXTURE.read_bytes())
        self.assertContains(self.owner.get(self.path()+'?version=2'),before)
        with ZipFile(io.BytesIO(self.owner.get(self.path('contract_download',3,'docx')).content)) as f:
            self.assertIn(changed,f.read('word/document.xml').decode())
        pdf = PdfReader(io.BytesIO(self.owner.get(self.path('contract_download',3,'pdf')).content))
        self.assertIn(changed,' '.join(' '.join(page.extract_text().split()) for page in pdf.pages))
        # A failed shorten can't replace either the original or manual edit.
        response = self.response({})
        response.update(status='incomplete',incomplete_details={'reason':'max_output_tokens'})
        provider = sdk.return_value.__enter__.return_value.responses.create
        provider.return_value = FakeResponse(response)
        attempt = self.action('shorten',source=src.pk,revision=3)
        self.assertEqual(self.action('shorten',source=src.pk,revision=3)['Location'],attempt['Location'])
        self.assertEqual(provider.call_count,1)
        contract.refresh_from_db()
        self.assertEqual(contract.current_revision,3)
        self.assertContains(self.owner.get(self.path()),changed)
        self.assertEqual(ContractAIRequest.objects.get().result['error'],'provider_output_limit')
        self.assertEqual(self.owner.get(self.path('contract_original',src.pk)).content,FIXTURE.read_bytes())


class FakeResponse:
    def __init__(self,data):
        self.data=data

    def model_dump(self, **kwargs):
        return self.data
