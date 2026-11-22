from uuid import uuid4

from django import template
from django.utils.translation import get_language

register = template.Library()


@register.simple_tag
def new_repair_token():
    """Distinct for each form, stable for a browser replay of that form."""
    return uuid4()


@register.filter
def repair_unit(value):
    if value == 'pack':
        return 'қапт.' if (get_language() or '').startswith('kk') else 'упак.'
    return value
