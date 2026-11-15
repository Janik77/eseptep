from django import template
from core.localization import system_text
register = template.Library()
register.filter('system_text', system_text)
