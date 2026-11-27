"""Typed, versioned material rules while retaining unedited reference formulas."""
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from .material_keys import BY_KEY, material_key
from .models import RecipeCalculator

LEGACY = 'legacy'
AREA = 'area'
COVERAGE = 'coverage'
FIXED = 'fixed'
FACTOR = 'factor'
LAYER = 'layer'
COUNT = 'count'
CONSUMPTION = 'consumption'
PACK_LENGTH = 'pack_length'
MODES = {LEGACY, AREA, COVERAGE, FIXED, FACTOR, LAYER, COUNT, CONSUMPTION, PACK_LENGTH}
MAX_LINE_TOTAL = Decimal('9999999999')
MAX_QUANTITY = Decimal('1000000000')
PACK_MASS_UNITS = {'мешок', 'мешков', 'меш', 'меш.'}
WHOLE_PURCHASE_UNITS = PACK_MASS_UNITS | {
    'шт', 'рул', 'рулон', 'рулонов', 'упак', 'упак.', 'компл.', 'компл', 'комплект',
    'рейс', 'пар', 'пара', 'туба', 'пачка', 'лист',
}


def scope_key(variant, key):
    return f'{variant}:{key}'


def active_rules(slug):
    entry = RecipeCalculator.objects.select_related('current').filter(pk=slug).first()
    if entry and entry.current_id:
        return str(entry.current_id), entry.current.rules
    return '', {}


def validate_snapshot(slug, result):
    # The same lock as price publication and estimate saving is already held.
    current = RecipeCalculator.objects.filter(pk=slug).values_list('current_id', flat=True).first()
    if str(current or '') != str((result.get('recipe_snapshot') or {}).get('version', '')):
        raise ValidationError(_('Настройки материалов изменились. Выполните расчёт заново.'))


def _quantity(rule, row, meta, unit):
    mode = rule['mode']
    original = Decimal(str(row['quantity'])) if row else Decimal('0')
    rate = Decimal(rule['rate']) if rule.get('rate') else None
    area = Decimal(str(meta['area']))
    user_inputs = meta.get('input', {})
    if mode == LEGACY:
        required = original
    elif mode == COVERAGE:
        required = area / rate
    elif mode == AREA:
        required = area * rate
    elif mode == LAYER:
        required = area * Decimal(str(meta['thickness'])) * rate
    elif mode == COUNT:
        required = Decimal(str(user_inputs[rule['count_field']])) * rate
    elif mode == CONSUMPTION:
        required = area * Decimal(str(meta['thickness'])) * rate / Decimal(rule['pack_mass'])
    elif mode == FACTOR:
        required = original * rate
    elif mode == PACK_LENGTH:
        required = original
    else:  # FIXED
        required = rate
    reserve = Decimal(rule['reserve']) if rule.get('reserve') else Decimal('0')
    if reserve:
        required *= 1 + reserve / 100
    if mode == PACK_LENGTH:
        required = (required / rate).to_integral_value(rounding=ROUND_CEILING) * rate
    if mode != LEGACY or reserve:
        rounding = rule.get('rounding', 'native')
        if mode == PACK_LENGTH:
            pass
        elif mode in {COVERAGE, CONSUMPTION} or rounding == 'up' or (rounding == 'native' and unit in WHOLE_PURCHASE_UNITS):
            required = required.to_integral_value(rounding=ROUND_CEILING)
        elif rounding == 'precision':
            required = required.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        else:
            from .services import _round_quantity
            required = Decimal(str(_round_quantity(float(required))))
    if not (0 <= required < MAX_QUANTITY):
        raise ValidationError(_('Норма даёт слишком большой объём.'))
    return required


def _numbers(rule, row, meta, master):
    unit = master['unit']
    quantity = _quantity(rule, row, meta, unit)
    price = Decimal(rule['price']) if rule.get('price') else Decimal(str(row.get('reference_price', 0) if row else 0))
    line_total = (quantity * price).quantize(Decimal('1'))
    if line_total > MAX_LINE_TOTAL:
        raise ValidationError(_('Норма даёт слишком большую стоимость.'))
    return quantity, price, line_total


def _output(rule, row, meta, key):
    output_key = rule.get('replacement') or key
    master = BY_KEY[output_key]
    quantity, price, total = _numbers(rule, row, meta, master)
    updated = {
        **(row or {}), 'material_key': output_key,
        'title': master['name'], 'unit': master['unit'],
        'quantity': int(quantity) if quantity == int(quantity) else float(quantity),
        'reference_price': int(price) if price == int(price) else float(price),
        'reference_total': int(total), 'price': int(price) if price == int(price) else float(price),
        'total': int(total),
    }
    if row and (output_key != key or quantity != Decimal(str(row['quantity']))):
        updated.pop('quantity_basis', None)  # old tile reference no longer describes this row
    updated['configured_rule'] = rule['mode']
    return updated


def _matches(rule, meta):
    when = rule.get('when') or {}
    return all(meta.get('input', {}).get(key) == value for key, value in when.items())


def _rows(rows, variant, meta, rules):
    matched, new = set(), []
    for row in rows:
        key = material_key(row['title'], row['unit'])
        rule = rules.get(scope_key(variant, key))
        if not rule or not _matches(rule, meta):
            new.append(row)
            continue
        matched.add(key)
        if not rule.get('disabled'):
            changed = _output(rule, row, meta, key)
            if changed['quantity'] > 0:
                new.append(changed)
    for scoped, rule in rules.items():
        expected, key = scoped.split(':', 1)
        if variant == expected and key not in matched and rule.get('add') and not rule.get('disabled') and _matches(rule, meta):
            new.append(_output(rule, None, meta, key))
    return new


def apply(slug, calculator, legacy, version, rules):
    if not version and not rules:
        return legacy
    changed = legacy
    if rules:
        from .services import _build_variant_result, _variant, _build_result
        meta = legacy['meta']
        builder_inputs = meta['input']
        if slug == 'nalivnoy-pol':
            mix = rules.get(scope_key('', 'mat_0078')) or {}
            if mix and (mix['mode'] != LEGACY or mix.get('replacement') or mix.get('disabled') or
                        Decimal(mix.get('reserve') or '0') != 0):
                # The original total mass is no longer a valid explanation of
                # the configured purchased quantity; don't show a stale metric.
                builder_inputs = {**builder_inputs, '_metrics': [
                    m for m in builder_inputs.get('_metrics', []) if m['label'] != 'Общий расход смеси'
                ]}
        if legacy.get('variants'):
            variants = {v['key']: _variant(v['key'], v['title'], v['description'],
                         _rows(v['materials'], v['key'], meta, rules), v['extra']) for v in legacy['variants']}
            changed = _build_variant_result(calculator, variants, legacy['selected_variant'], builder_inputs,
                                            meta['area'], meta['rooms'], meta['thickness'], legacy['summary'])
        else:
            rows = _rows(legacy['materials'], '', meta, rules)
            if slug == 'laminat-spc-parket':
                from .services import _build_flooring_result
                changed = _build_flooring_result(calculator, rows, builder_inputs, meta['area'],
                                                 legacy['summary'], legacy['warning'])
            else:
                changed = _build_result(
                    calculator, rows, builder_inputs, meta['area'], meta['rooms'], meta['thickness'], meta['segment'],
                    {'label': legacy['segment_label'], 'material': 1.0, 'labor': 0}, legacy['summary'])
            # The base row price already includes the old segment multiplier.
            # Keep it and labour contribution intact rather than scaling twice.
            if legacy['labor_total']:
                changed['labor_total'] = changed['reference_labor_total'] = legacy['labor_total']
                changed['grand_total'] += legacy['labor_total']
                changed['reference_grand_total'] += legacy['labor_total']
        # Preserve typed legacy parameters and other metadata; replace all
        # totals/variants/context fields from the canonical result builders.
        changed = {**legacy, **changed}
        totals = [v['total'] for v in changed.get('variants', [])] or [changed['grand_total']]
        if any(t > MAX_LINE_TOTAL for t in totals):
            raise ValidationError(_('Нормы дают слишком большую стоимость.'))
    changed['recipe_snapshot'] = {'version': str(version), 'calculator': slug}
    return changed
