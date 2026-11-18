"""Separate, versioned admin quotation. Legacy construction/reference formulas unchanged."""
from decimal import Decimal, ROUND_HALF_UP
from .models import PriceBook
from .material_keys import material_key


def quotation(slug, variant, materials, book):
    if book is None:
        return None
    entries = {(p.material_key, p.unit): p for p in book.entries.filter(calculator_slug=slug, variant_key=variant)}
    rows, missing, total = [], [], Decimal('0')
    for row in materials:
        quantity = Decimal(str(row['quantity']))
        if quantity <= 0:
            continue
        price = entries.get((material_key(row['title'], row['unit']), row['unit']))
        if price is None:
            missing.append({'material_title': row['title'], 'unit_label': row['unit']})
            continue
        line_total = (quantity * price.price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total += line_total
        rows.append({'material_key': price.material_key, 'material_title': row['title'], 'unit_label': row['unit'], 'quantity': str(quantity),
                     'unit_price': str(price.price), 'line_total': str(line_total)})
    return {'store_name': book.store_name, 'version': book.version, 'source_note': book.source_note,
            'price_date': book.price_date.isoformat(), 'currency': 'KZT', 'method_version': 'reference-quantities@pilot-exact-match-v2',
            'variant_key': variant, 'rows': rows, 'missing': missing, 'complete': not missing and bool(rows),
            'subtotal': str(total), 'coverage': len(rows), 'required': len(rows) + len(missing)}


def attach_quotation(slug, result):
    book = PriceBook.objects.filter(is_active=True, published_at__isnull=False).first()
    variants = result.get('variants')
    if variants:
        for variant in variants:
            variant['admin_quote'] = quotation(slug, variant['key'], variant['materials'], book)
        result['admin_quote'] = next((v['admin_quote'] for v in variants if v['key'] == result['selected_variant']), None)
    else:
        result['admin_quote'] = quotation(slug, '', result['materials'], book)


def lock_price_configuration():
    """Caller must hold atomic(). A no-op UPDATE also serializes SQLite writers."""
    from django.db import connection
    from django.db.models import F
    from .models import PriceConfigurationLock
    if not connection.in_atomic_block:
        raise RuntimeError('Price configuration lock requires an atomic transaction')
    if PriceConfigurationLock.objects.filter(pk=1).update(revision=F('revision')) != 1:
        raise RuntimeError('Price configuration migration is missing')


def validate_snapshot_version(result):
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext
    lock_price_configuration()
    active = PriceBook.objects.filter(is_active=True, published_at__isnull=False).first()
    current_version = active.version if active else ''
    snapshot_version = (result.get('admin_quote') or {}).get('version', '')
    if snapshot_version != current_version:
        raise ValidationError(gettext('Прайс изменился. Проверьте новый расчёт и сохраните снова.'))
