"""Shared input contract; limits are application bounds, not construction norms."""
from decimal import Decimal, InvalidOperation

# Keep estimates within persistence precision and limit unreasonable requests.
MAX_AREA = 10000
MAX_COUNT = 100
VARIANT_CALCULATORS = {
    'elektrika', 'santehnika', 'gipsokarton-potolok', 'plitka-keramogranit',
    'malyarka', 'natyazhnoy-potolok', 'teplyy-pol',
}


class InputValidationError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__('; '.join(errors.values()))


def validate_fields(fields, data):
    """Return normalized strings; raise field-keyed errors without changing data.

    Missing fields are errors. Decimal commas are accepted. Numbers must be finite,
    within inclusive bounds, and have at most two fractional digits (DB precision).
    Integer fields reject fractions rather than silently truncating them.
    """
    cleaned, errors = {}, {}
    for field in fields:
        name = field['name']
        raw = str(data.get(name, '')).strip()
        label = field['label']
        if field.get('type') == 'select':
            if raw not in {str(option['value']) for option in field['options']}:
                errors[name] = f'{label}: выберите значение из списка.'
            else:
                cleaned[name] = raw
            continue
        integer = field.get('step') == 1
        minimum = Decimal(str(field.get('min', 1)))
        maximum = Decimal(str(field.get('max', MAX_COUNT if integer else MAX_AREA)))
        try:
            if not raw or len(raw) > 64:
                raise ValueError
            number = Decimal(raw.replace(',', '.'))
            if not number.is_finite() or not minimum <= number <= maximum:
                raise ValueError
            if integer and number != number.to_integral_value():
                errors[name] = f'{label}: введите целое число от {minimum} до {maximum}.'
                continue
            if number != number.quantize(Decimal('0.01')):
                errors[name] = f'{label}: укажите не более двух знаков после запятой.'
                continue
            cleaned[name] = format(number, 'f')
        except (InvalidOperation, ValueError):
            errors[name] = f'{label}: введите число от {minimum} до {maximum}.'
    if errors:
        raise InputValidationError(errors)
    return cleaned


def validate_calculator_input(calculator, data):
    cleaned = validate_fields(calculator['fields'], data)
    if 'selected_variant' in data:
        allowed = ('base', 'optimal', 'maximum') if calculator['slug'] == 'demontazh' else (
            ('economy', 'comfort', 'business') if calculator['slug'] in VARIANT_CALCULATORS else ()
        )
        if data['selected_variant'] not in allowed:
            raise InputValidationError({'selected_variant': 'Вариант: выберите доступный вариант расчёта.'})
        cleaned['selected_variant'] = data['selected_variant']
    return cleaned
