"""Opt-in catalogue candidates, never calculation inputs or purchase recommendations.

Name and unit equality cannot establish specification/pack compatibility. Deliberately
no fuzzy matching, currency inference, stock inference or unit/pack conversions.
"""
from accounts.models import SupplierMaterial


def material_offers(materials):
    groups = []
    for row in materials:
        if not row.get('quantity') or row['quantity'] <= 0:
            continue
        products = SupplierMaterial.objects.filter(
            is_published=True, supplier__is_active=True,
            supplier__user__is_active=True, supplier__user__profile__role='supplier',
            name=row['title'], unit=row['unit'], price__gt=0,
        ).select_related('supplier').order_by('-updated_at', 'pk')[:3]
        groups.append({
            'material_title': row['title'], 'quantity': row['quantity'], 'unit_label': row['unit'],
            'products': [{'product_name': p.name, 'supplier_name': p.supplier.company_name,
                          'unit_label': p.unit, 'price': p.price,
                          'reported_stock': p.stock_status, 'reported_delivery': p.delivery_time,
                          'updated_at': p.updated_at} for p in products],
        })
    return groups


def attach_offers(result):
    """Call only after any persistence step; no offer data enters saved snapshots."""
    if result.get('variants'):
        for variant in result['variants']:
            variant['offers'] = material_offers(variant['materials'])
    else:
        result['offers'] = material_offers(result['materials'])
