"""Explicit non-production presentation mode, no external delivery integrations."""
from django.conf import settings


def demo_context(request):
    return {'demo_mode': settings.ESEPTEP_DEMO_MODE}
