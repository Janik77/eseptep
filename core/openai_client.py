"""One backend-only SDK boundary. No automatic retries, tools, secrets or paid smoke tests."""
import json
from django.conf import settings
from openai import OpenAI

ALLOWED_MODELS = {'gpt-4.1-mini-2025-04-14', 'gpt-5.4-mini-2026-03-17'}
class AIConfigurationError(Exception):
    pass

def validate_configuration():
    key = settings.OPENAI_API_KEY.strip()
    if not key or key.startswith(('REPLACE_', 'PASTE_')) or not settings.OPENAI_LIVE_CONFIRMED:
        raise AIConfigurationError('not_configured')
    if settings.OPENAI_MODEL not in ALLOWED_MODELS:
        raise AIConfigurationError('unsupported_model')

def responses_create(**payload):
    validate_configuration()
    payload['model'] = settings.OPENAI_MODEL
    payload['store'] = False
    payload['max_output_tokens'] = min(int(payload.get('max_output_tokens', 1200)), settings.OPENAI_MAX_OUTPUT_TOKENS)
    # Fixed official endpoint; never forward credentials to an environment-supplied proxy URL.
    with OpenAI(api_key=settings.OPENAI_API_KEY, base_url='https://api.openai.com/v1',
                timeout=settings.OPENAI_TIMEOUT_SECONDS, max_retries=0) as client:
        response = client.responses.create(**payload)
        data = response.model_dump(mode='json')
    if len(json.dumps(data).encode()) > 65536:
        raise ValueError('response_limit')
    return data
