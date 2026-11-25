from django import template
from django.http import Http404
from repairs.services import scoped_repair

register = template.Library()


@register.simple_tag
def may_open_repair(user, project_id):
    try:
        scoped_repair(user, project_id)
    except Http404:
        return False
    return True


@register.simple_tag
def contract_entry(user, project_id):
    from repairs.contract_views import entry_for
    return entry_for(user,project_id)
