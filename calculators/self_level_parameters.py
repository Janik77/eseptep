"""One typed parameter, no new engineering methodology or automatic unit conversion."""
from .models import SelfLevelMixEdition

LEGACY_VERSION = 'legacy-selflevel-15@eb785d3'


def current_parameters():
    edition = SelfLevelMixEdition.objects.filter(is_active=True, published_at__isnull=False).first()
    return {
        'scope': 'nalivnoy-pol', 'version': edition.version if edition else LEGACY_VERSION,
        'source_kind': 'admin' if edition else 'historical',
        'source_note': edition.source_note if edition else '',
        'source_date': edition.source_date.isoformat() if edition else '',
        'consumption': str(edition.consumption) if edition else '15',
        'unit': 'kg_per_m2_cm', 'bag_mass_kg': 25,
        'method': 'ceil(area_m2 * thickness_cm * consumption / 25)',
        'method_version': 'selflevel-reference-method@eb785d3',
    }


def validate_snapshot(slug, result):
    # Caller already holds the common price/configuration lock in atomic().
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext
    if slug == 'nalivnoy-pol':
        version = (result.get('parameter_snapshot') or {}).get('version')
        if version != current_parameters()['version']:
            raise ValidationError(gettext('Параметр расхода изменился. Проверьте новый расчёт и сохраните снова.'))
