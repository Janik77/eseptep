from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from .forms import MasterProfileForm, MasterResponseForm, SupplierMaterialForm, SupplierResponseForm
from .models import ClientProject, MasterProfile, MasterResponse, ServiceRequest, SupplierResponse, UserProfile


class AccountWorkflowTests(TestCase):
    def setUp(self):
        self.owner = self.user('owner', 'client')
        self.other = self.user('other', 'client')
        self.master = self.user('master', 'master')
        self.supplier = self.user('supplier', 'supplier')
        self.project = ClientProject.objects.create(user=self.owner, title='Owned', city='Астана', area_m2=60, rooms=2)
        self.request = ServiceRequest.objects.create(client=self.owner, project=self.project, request_type='master')

    def user(self, name, role):
        user = User.objects.create_user(username=name, password='test-password')
        UserProfile.objects.create(user=user, role=role)
        return user

    def post_offer(self, user, dashboard, **changes):
        self.client.force_login(user)
        return self.client.post(reverse('accounts:dashboard_' + dashboard),
                                {'request_id': self.request.pk, 'price_from': '100', 'total_price': '100', **changes})

    def test_master_offer_and_no_synthetic_rating(self):
        self.assertEqual(self.post_offer(self.master, 'master').status_code, 302)
        self.assertEqual(MasterResponse.objects.count(), 1)
        self.assertEqual(MasterProfile.objects.get(user=self.master).rating, 0)

    def test_post_rechecks_request_type_and_status(self):
        for user, dashboard, wrong_type in [(self.master, 'master', 'supplier'), (self.supplier, 'supplier', 'master')]:
            self.request.request_type = wrong_type
            self.request.save()
            self.assertEqual(self.post_offer(user, dashboard).status_code, 404)
            self.request.request_type = dashboard
            self.request.status = 'closed'
            self.request.save()
            self.assertEqual(self.post_offer(user, dashboard).status_code, 404)
            self.request.status = 'new'
        self.assertFalse(MasterResponse.objects.exists())
        self.assertFalse(SupplierResponse.objects.exists())

    def test_wrong_role_is_forbidden(self):
        self.assertEqual(self.post_offer(self.owner, 'master').status_code, 403)

    def test_negative_offer_is_not_saved(self):
        self.assertEqual(self.post_offer(self.master, 'master', price_from='-1').status_code, 200)
        self.assertFalse(MasterResponse.objects.exists())

    def test_price_fields_reject_negative_nan_and_infinity(self):
        for form, field in [(MasterResponseForm, 'price_from'), (SupplierResponseForm, 'total_price'), (SupplierMaterialForm, 'price')]:
            for value in ['-1', 'NaN', 'Infinity']:
                bound = form({field: value})
                self.assertFalse(bound.is_valid())
                self.assertIn(field, bound.errors)

    def test_rating_not_editable(self):
        self.assertNotIn('rating', MasterProfileForm().fields)

    def test_response_owner_and_terminal_status(self):
        self.post_offer(self.master, 'master')
        response = MasterResponse.objects.get()
        payload = {'response_type': 'master', 'response_id': response.pk, 'response_action': 'accept'}
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('accounts:dashboard_client'), payload).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('accounts:dashboard_client'), payload).status_code, 302)
        self.assertEqual(self.client.post(reverse('accounts:dashboard_client'), payload).status_code, 400)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'accepted')

    def test_logout_requires_post_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        url = reverse('accounts:logout')
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url).status_code, 403)
        page = client.get(reverse('accounts:dashboard_client'))
        self.assertContains(page, 'Кабинет')
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(url, {'csrfmiddlewaretoken': token}).status_code, 302)
        self.assertNotIn('_auth_user_id', client.session)

    def test_unknown_action_is_bad_request(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('accounts:dashboard_client'), {'response_action': 'invented'}).status_code, 400)

    def test_unbounded_or_invalid_workflow_ids_are_bad_requests(self):
        for value in ['9' * 5000, str(2**63), '0', '-1', '１２', '', '1.5']:
            with self.subTest(value=value[:25]):
                for user, dashboard in [(self.master, 'master'), (self.supplier, 'supplier')]:
                    self.assertEqual(self.post_offer(user, dashboard, request_id=value).status_code, 400)
                self.client.force_login(self.owner)
                response = self.client.post(reverse('accounts:dashboard_client'), {
                    'response_id': value, 'response_type': 'master', 'response_action': 'accept'})
                self.assertEqual(response.status_code, 400)
        self.assertFalse(MasterResponse.objects.exists())
        self.assertFalse(SupplierResponse.objects.exists())
