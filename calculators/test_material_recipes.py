from io import BytesIO
from itertools import product

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.translation import override
from pypdf import PdfReader

from accounts.models import ClientProject, UserProfile
from .admin_recipes import CATALOG
from .definitions import CALCULATORS, CALCULATORS_BY_SLUG
from .material_keys import BY_KEY, material_key
from .models import RecipeCalculator, RecipeEdition
from .self_level_parameters import LEGACY_VERSION
from .services import calculate_base, calculate_materials
from . import services
from .validation import InputValidationError, MAX_AREA, MAX_COUNT


class RecipeWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = User.objects.create_user('editor', is_staff=True)
        cls.editor.groups.add(Group.objects.get(name='Редактор калькуляторов'))
        cls.client_user = User.objects.create_user('review@eseptep.test')
        UserProfile.objects.get_or_create(user=cls.client_user, defaults={'role':UserProfile.Role.CLIENT})
        cls.project = ClientProject.objects.create(user=cls.client_user,title='Ремонт квартиры',
                                                  city='Шымкент',area_m2=250,rooms=2)
        cls.calculator = CALCULATORS_BY_SLUG['nalivnoy-pol']
        cls.admin_url = reverse('admin:calculators_recipecalculator_change', args=['nalivnoy-pol'])
        cls.calc_url = reverse('calculators:detail', args=['nalivnoy-pol'])

    def setUp(self):
        self.admin = Client()
        self.admin.force_login(self.editor)
        self.client.force_login(self.client_user)

    def _result(self, area='250'):
        response = self.client.post(self.calc_url, {'area':area,'thickness':'2'})
        self.assertEqual(response.status_code,200)
        return response.context['result'], response.context['submission_token']

    def _row(self, result, name='Грунтовка 10 кг'):
        return next(row for row in result['materials'] if row['title']==name)

    def _submit(self, token, recipe='', *, area='250'):
        return self.client.post(self.calc_url, {'area':area,'thickness':'2','action':'save_estimate',
            'project_id':self.project.pk,'submission_token':token,'recipe_version':recipe,
            'parameter_version':LEGACY_VERSION,'price_book_version':''})

    def _draft(self, rate='50,00', price='400', revision='0'):
        return self.admin.post(self.admin_url, {'action':'save','revision':revision, 'material':'mat_0034',
            'variant':'','mode':'coverage','rate':rate,'price':price,'rounding':'native','source':'Тестовая упаковка'})

    def _preview(self, area='250', rollback=''):
        response = self.admin.post(self.admin_url, {'action':'preview', 'input_area':area,
                                                 'input_thickness':'2','rollback':rollback})
        self.assertEqual(response.status_code,200)
        return response

    def _publish(self, response):
        return self.admin.post(self.admin_url, {'action':'publish','revision':str(response.context['entry'].draft_revision),
                                            'token':response.context['token']})

    def _pdf(self, record):
        out = self.client.get(reverse('calculators:saved_pdf', args=[record.pk]))
        self.assertEqual(out.status_code,200)
        return ' '.join(' '.join(page.extract_text().split())
                        for page in PdfReader(BytesIO(out.content)).pages)

    def test_home_role_and_primer_in_three_calculation_paths(self):
        before, token = self._result()
        self.assertEqual(self._row(before)['quantity'],125)
        self.assertEqual(before['grand_total'],984200)
        old = self._submit(token)
        self.assertEqual(old.status_code,302)
        old_calc = self.project.calculations.get()
        self.assertEqual(self._row(old_calc.result_data)['quantity'],125)
        self.assertEqual(self._draft().status_code,302)
        self.assertEqual(self._row(self._result()[0])['quantity'],125)
        preview = self._preview()
        self.assertIsNotNone(preview.context['token'])
        change = preview.context['preview'][0]['lines'][0]
        self.assertEqual((change['before']['quantity'],change['after']['quantity']), (125,5))
        self.assertEqual(change['after']['reference_total'],2000)
        self.assertEqual(self._publish(preview).status_code,302)
        self.assertEqual(self._submit(token).status_code,302)  # original receipt stays idempotent
        entry = RecipeCalculator.objects.get(pk='nalivnoy-pol')
        self.assertEqual(entry.current.author, self.editor)
        for area, qty, cost in [('250',5,2000),('251',6,2400),('20',1,400)]:
            result, token = self._result(area)
            row = self._row(result)
            self.assertEqual((row['quantity'],row['total']), (qty,cost))
            self.assertEqual(result['grand_total'],sum(x['total'] for x in result['materials']))
            self.assertIn(f'{qty} шт',result['saved_list'])
            if area=='250':
                self.assertEqual(self._submit(token,str(entry.current_id)).status_code,302)
        new = self.project.calculations.exclude(pk=old_calc.pk).get()
        self.assertEqual(new.result_data['recipe_snapshot']['version'],str(entry.current_id))
        self.assertRegex(self._pdf(old_calc), r'Грунтовка 10 кг 125 шт 50\s*000')
        self.assertRegex(self._pdf(new), r'Грунтовка 10 кг 5 шт 2\s*000')
        self.assertEqual(self._publish(self._preview(rollback='0')).status_code,302)
        self.assertEqual(self._row(self._result()[0])['quantity'],125)
        self.assertEqual(RecipeEdition.objects.filter(calculator=entry).count(),2)
        old_calc.refresh_from_db()
        self.assertEqual(self._row(old_calc.result_data)['quantity'],125)
        self.assertEqual(self.client.get(self.admin_url).status_code,302)
        staff = User.objects.create_user('unrelated-staff',is_staff=True)
        self.admin.force_login(staff)
        self.assertEqual(self.admin.get(self.admin_url).status_code,403)

    def test_validation_and_stale_preview(self):
        result = self._draft(rate='0')
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.context['form'].errors.get('rate'))
        result = self._draft(rate='-5')
        self.assertTrue(result.context['form'].errors.get('rate'))
        self.assertEqual(self._draft().status_code,302)
        preview = self._preview()
        self.assertEqual(self._draft(rate='60',revision='1').status_code,302)
        response = self._publish(preview)
        self.assertContains(response,'Черновик изменился')
        self.assertFalse(RecipeEdition.objects.exists())

    def test_all_twelve_have_coverage_and_no_default_drift(self):
        self.assertEqual(RecipeCalculator.objects.count(),12)
        self.assertEqual(set(CATALOG),{c['slug'] for c in CALCULATORS})
        for definition in CALCULATORS:
            slug = definition['slug']
            fields = definition['fields']
            options = [[str(o['value']) for o in f['options']] if f.get('type')=='select'
                       else list(dict.fromkeys(str(v) for v in (f['default'],f.get('min',1),
                                 f.get('max', MAX_COUNT if f.get('step')==1 else MAX_AREA))))
                       for f in fields]
            test_cases = [dict(zip((f['name'] for f in fields),values)) for values in product(*options)]
            cases = {
                'elektrika': ({'area':a,'rooms':b} for a,b in services.ELECTRIC_REFERENCE_MATRIX),
                'gipsokarton-potolok': ({'construction_type':t,'area':a,'rooms':b} for t,m in services.DRYWALL_REFERENCE_MATRIX.items() for a,b in m),
                'nalivnoy-pol': ({'area':a,'thickness':b} for a,b in services.SELF_LEVEL_REFERENCE_MATRIX),
                'plitka-keramogranit': ({'area':a,'zone':b,'tile_format':c} for a,b,c in services.TILE_REFERENCE_MATRIX),
                'laminat-spc-parket': ({'covering_type':t,'area':a} for t,m in services.FLOORING_REFERENCE_TOTALS.items() for a in m),
                'malyarka': ({'type':t,'floor_area':a} for t,m in services.PAINTING_REFERENCE_MATRIX.items() for a in m),
                'natyazhnoy-potolok': ({'area':a,'rooms':b} for a,b in services.CEILING_REFERENCE_TOTALS),
                'teplyy-pol': ({'type':t,'area':a} for t,m in services.WARM_FLOOR_REFERENCE_TOTALS.items() for a in m),
            }
            test_cases.extend([{**test_cases[0],**{k:str(v) for k,v in case.items()}} for case in cases.get(slug,())])
            for inputs in test_cases:
                try:
                    result = calculate_materials(definition,inputs)
                except InputValidationError:
                    continue
                self.assertEqual(result,calculate_base(definition,inputs))
                for scope in result.get('variants',[dict(result,key='')]):
                    for row in scope['materials']:
                        self.assertIn(material_key(row['title'],row['unit']),CATALOG[slug][scope['key']],
                                      (slug,inputs,scope['key'],row['title']))
            self.assertTrue(all(key in BY_KEY for rows in CATALOG[slug].values() for key in rows))

    def test_selector_variant_isolation_and_whole_plan_group_quantity(self):
        from projects.whole_plan import calculate_snapshot
        from .material_recipes import scope_key
        definition = CALCULATORS_BY_SLUG['plitka-keramogranit']
        inputs = {'area':'20','zone':'floor','tile_format':'60x60'}
        before = calculate_base(definition,inputs)
        old_row = before['variants_by_key']['comfort']['materials'][0]
        key = material_key(old_row['title'],old_row['unit'])
        rooms = [{'name':'Ванная','index':0,'area':'20','finish':'tile'}]
        old_plan = calculate_snapshot(rooms,111)
        model = RecipeCalculator.objects.get(pk=definition['slug'])
        model.current = RecipeEdition.objects.create(calculator=model,author=self.editor,author_label='editor',rules={
            scope_key('comfort',key):{'mode':'area','rate':'1.5','rounding':'up','when':{'zone':'floor'},'source':'test'},
        })
        model.save(update_fields=['current'])
        result = calculate_materials(definition,inputs)
        changed = result['variants_by_key']['comfort']['materials'][0]
        self.assertEqual(changed['quantity'],30)
        self.assertNotIn('quantity_basis',changed)
        self.assertEqual(result['variants_by_key']['business'],before['variants_by_key']['business'])
        wall = {**inputs,'zone':'walls'}
        self.assertEqual(calculate_materials(definition,wall)['variants'],calculate_base(definition,wall)['variants'])
        new_plan = calculate_snapshot(rooms,111)
        self.assertEqual(new_plan['recipe_versions'][definition['slug']],str(model.current_id))
        prior_qty = next(p['quantity'] for p in old_plan['procurement'] if p['material_key']==key)
        current_qty = next(p['quantity'] for p in new_plan['procurement'] if p['material_key']==key)
        self.assertEqual((prior_qty,current_qty),(str(old_row['quantity']),'30'))
        self.assertIsNone(next(p for p in new_plan['procurement'] if p['material_key']==key)['unit_price'])
