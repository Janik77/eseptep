"""Explicit non-production presentation mode, no external delivery integrations."""
from django.conf import settings


def demo_context(request):
    return {'demo_mode': settings.ESEPTEP_DEMO_MODE,
            'closed_pilot_mode': getattr(settings, 'ESEPTEP_CLOSED_PILOT', False),
            'contract_offline_mock': getattr(settings, 'CONTRACT_OFFLINE_MOCK', False)}
