"""Exactly three typed monetary rates. No arbitrary formulas/consumption overrides."""
from decimal import Decimal, ROUND_HALF_EVEN
from calculators.models import RenovationRateEdition

LEGACY_VERSION = 'historical-code@170e0a4'
LEGACY_RATES = {'economy': '120000', 'standard': '170000', 'premium': '250000'}


def rate_configuration(*, historical=False):
    edition = None if historical else RenovationRateEdition.objects.filter(is_active=True, published_at__isnull=False).first()
    if edition:
        return {'version': edition.version, 'source_note': edition.source_note,
                'effective_date': edition.effective_date.isoformat(), 'source_kind': 'admin',
                'unit': 'KZT/m2', 'rates': {key: str(getattr(edition, key + '_rate')) for key in LEGACY_RATES}}
    return {'version': LEGACY_VERSION, 'source_note': '', 'effective_date': '', 'source_kind': 'historical',
            'unit': 'KZT/m2', 'rates': dict(LEGACY_RATES)}


def renovation_estimate(area, level, configuration):
    """Existing whole-tenge half-even total policy; units and variant stay explicit."""
    rate = Decimal(configuration['rates'][level])
    quantity = Decimal(str(area))
    total = (quantity * rate).quantize(Decimal('1'), rounding=ROUND_HALF_EVEN)
    return {'area': str(quantity), 'repair_level_key': level, 'rate_per_m2': str(rate), 'total': int(total),
            'configuration': configuration, 'method_version': 'area-times-rate-half-even-v1'}
