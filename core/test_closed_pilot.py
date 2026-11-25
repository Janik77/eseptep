from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .closed_pilot import INVITED_GROUP, PAID_GROUP, pilot_member


@override_settings(MIDDLEWARE=[*settings.MIDDLEWARE, 'core.closed_pilot.ClosedPilotAccess'],
                   ESEPTEP_CLOSED_PILOT=True)
class HostedBoundaryTests(TestCase):
    def test_invitation_current_membership_and_no_public_examples(self):
        browser = Client()
        home = reverse('core:home')
        login = reverse('accounts:login')
        self.assertEqual(browser.get(home).status_code, 302)
        self.assertEqual(browser.get(login).status_code, 200)
        self.assertEqual(browser.get(reverse('accounts:register')).status_code, 404)
        self.assertEqual(browser.post(reverse('projects:upload')).status_code, 404)
        account = get_user_model().objects.create_user(username='local-test-invite')
        browser.force_login(account)
        self.assertEqual(browser.get(home).status_code, 404)
        invited = Group.objects.create(name=INVITED_GROUP)
        paid = Group.objects.create(name=PAID_GROUP)
        account.groups.add(paid)
        self.assertFalse(pilot_member(account, paid=True))
        account.groups.add(invited)
        response = browser.get(home)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(browser.post(reverse('projects:choose_sample'), {'sample':'studio'}).status_code, 404)
        self.assertTrue(pilot_member(account, paid=True))
        account.groups.remove(paid)
        self.assertFalse(pilot_member(account, paid=True))
        account.groups.remove(invited)
        self.assertEqual(browser.get(home).status_code, 404)

    @override_settings(LOCAL_AI_BUDGET_PATH='',OPENAI_LIVE_CONFIRMED=True,
                       OPENAI_API_KEY='synthetic-only',OPENAI_MODEL='gpt-6.1-sol')
    @patch('core.openai_client.OpenAI')
    def test_no_hosted_provider_access_when_no_existing_ledger(self, sdk):
        from .openai_client import AIConfigurationError, responses_create
        with self.assertRaisesRegex(AIConfigurationError, 'budget_missing'):
            responses_create(input='synthetic', max_output_tokens=1800)
        sdk.assert_not_called()
