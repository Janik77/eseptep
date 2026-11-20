"""Strict, bounded first floor price list. No file retention or publication."""
import csv
import io
import re
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import MaterialPrice, PriceBook
from .pricing import lock_price_configuration

HEADERS = ['material', 'unit', 'price_basis', 'pack_coverage', 'price_kzt']
PILOT_ROWS = {
    'laminate': ('laminat-spc-parket', '', 'mat_0067', 'м²'),
    'underlay': ('laminat-spc-parket', '', 'mat_0095', 'м²'),
    'skirting': ('laminat-spc-parket', '', 'mat_0090', 'м'),
    'tile_60x60': ('plitka-keramogranit', 'comfort', 'mat_0091', 'м²'),
}
MAX_BYTES = 16_384


def _positive(raw, whole, fractional):
    if not re.fullmatch(rf'[0-9]{{1,{whole}}}(?:[.,][0-9]{{1,{fractional}}})?', raw):
        raise ValueError('Expected a positive decimal without currency or thousands separators.')
    value = Decimal(raw.replace(',', '.'))
    if value <= 0:
        raise ValueError('Expected a positive decimal.')
    return value


def parse_floor_prices(data):
    if len(data) > MAX_BYTES:
        raise ValueError('CSV exceeds 16 KiB.')
    try:
        reader = csv.reader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
        if next(reader, []) != HEADERS:
            raise ValueError('CSV header must be: ' + ','.join(HEADERS))
        seen, rows = set(), []
        for values in reader:
            if not values:
                continue
            try:
                material, unit, basis, coverage_text, price = [x.strip() for x in values]
                if material not in PILOT_ROWS or material in seen:
                    raise ValueError('Unknown or duplicate pilot material.')
                slug, variant, key, expected_unit = PILOT_ROWS[material]
                if unit != expected_unit:
                    raise ValueError(f'Use canonical unit {expected_unit}; put pack in price_basis, not unit.')
                if basis == 'pack':
                    coverage = _positive(coverage_text, 6, 4)
                elif basis == 'canonical':
                    coverage = _positive(coverage_text, 6, 4) if coverage_text else None
                else:
                    raise ValueError('Use canonical (optional coverage) or pack (positive coverage required).')
                rows.append(dict(calculator_slug=slug, variant_key=variant, material_key=key, unit=unit,
                    price_basis=basis, pack_coverage=coverage, price=_positive(price, 10, 2)))
                seen.add(material)
            except ValueError as exc:
                raise ValueError(f'CSV row {reader.line_num}: {exc}') from exc
    except (UnicodeError, csv.Error) as exc:
        raise ValueError('Expected a valid UTF-8, comma-separated CSV.') from exc
    if not rows:
        raise ValueError('The price list is empty.')
    return rows


def import_floor_prices(data, *, store, version, source, date_text, write=False):
    rows = parse_floor_prices(data)
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', date_text):
        raise ValueError('Expected ISO date YYYY-MM-DD.')
    fields = dict(store_name=store.strip(), version=version.strip(), source_note=source.strip(),
                  price_date=date.fromisoformat(date_text))
    draft = PriceBook(**fields)
    draft.full_clean()
    for values in rows:
        MaterialPrice(book=draft, **values).full_clean(exclude=['book'])
    if not write:
        return None, len(rows)
    with transaction.atomic():
        lock_price_configuration()
        # Recheck under the same lock as publication.
        draft.full_clean()
        draft.save()
        for values in rows:
            entry = MaterialPrice(book=draft, **values)
            entry.full_clean()
            entry.save()
    return draft, len(rows)
