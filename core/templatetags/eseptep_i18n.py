from django import template
from core.localization import system_text
register = template.Library()
register.filter('system_text', system_text)


@register.filter
def money(value):
    """Presentation only: preserve decimal kopecks and group tenge consistently."""
    from decimal import Decimal, InvalidOperation
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            return value
        return format(amount, ',f').rstrip('0').rstrip('.') .replace(',', ' ').replace('.', ',') if '.' in format(amount, 'f') else format(amount, ',f').replace(',', ' ')
    except (InvalidOperation, ValueError, TypeError):
        return value
