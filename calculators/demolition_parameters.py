"""One existing preliminary film ratio, not a material/product specification."""
from .models import DemolitionFilmEdition

LEGACY_VERSION = 'legacy-demolition-film-1.20@15ea35e'
STALE_MESSAGE = 'Параметр защитной плёнки изменился. Проверьте новый расчёт и сохраните снова.'

def current_parameters():
    edition = DemolitionFilmEdition.objects.filter(is_active=True, published_at__isnull=False).first()
    return {
        'scope': 'demontazh', 'version': edition.version if edition else LEGACY_VERSION,
        'source_kind': 'admin' if edition else 'historical',
        'source_note': edition.source_note if edition else '',
        'source_date': edition.source_date.isoformat() if edition else '',
        'consumption': str(edition.consumption) if edition else '1.20',
        'unit': 'm2_per_m2',
        'method': 'ceil(area_m2 * consumption)',
        'method_version': 'demolition-reference-method@15ea35e',
    }

def validate_snapshot(slug, result):
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext
    if slug == 'demontazh' and (result.get('parameter_snapshot') or {}).get('version') != current_parameters()['version']:
        raise ValidationError(gettext(STALE_MESSAGE))
