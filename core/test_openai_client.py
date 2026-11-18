from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .openai_client import responses_create, validate_configuration, AIConfigurationError

class SDKBoundaryTests(SimpleTestCase):
    @override_settings(OPENAI_API_KEY='PASTE_EXISTING_KEY_HERE',OPENAI_LIVE_CONFIRMED=True)
    def test_placeholder_blocked(self):
        with self.assertRaises(AIConfigurationError):validate_configuration()

    @override_settings(OPENAI_API_KEY='mock-only',OPENAI_LIVE_CONFIRMED=True,OPENAI_MODEL='gpt-5.4-mini-2026-03-17',OPENAI_MAX_OUTPUT_TOKENS=1800,OPENAI_TIMEOUT_SECONDS=45)
    @patch('core.openai_client.OpenAI')
    def test_official_sdk_fixed_endpoint_no_retry_bounded_output(self,sdk):
        sdk.return_value.__enter__.return_value.responses.create.return_value.model_dump.return_value={'status':'completed'}
        self.assertEqual(responses_create(input='test',max_output_tokens=99999,store=True),{'status':'completed'})
        self.assertEqual(sdk.call_args.kwargs['max_retries'],0)
        self.assertEqual(sdk.call_args.kwargs['base_url'],'https://api.openai.com/v1')
        kwargs=sdk.return_value.__enter__.return_value.responses.create.call_args.kwargs
        self.assertEqual(kwargs['max_output_tokens'],1800);self.assertFalse(kwargs['store'])
        with override_settings(OPENAI_MODEL='unpriced-expensive-model'):
            with self.assertRaises(AIConfigurationError):responses_create(input='no')
