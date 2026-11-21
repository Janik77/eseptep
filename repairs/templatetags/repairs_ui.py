from uuid import uuid4

from django import template

register = template.Library()


@register.simple_tag
def new_repair_token():
    """Distinct for each form, stable for a browser replay of that form."""
    return uuid4()
