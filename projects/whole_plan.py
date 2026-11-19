"""Whole-apartment floor estimate using existing calculators and published prices.
No AI call on recalculation, no wall-area inference, no assumed market prices.
"""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.services import calculate_materials
from calculators.models import PriceBook
from calculators.pricing import quotation, lock_price_configuration
from .models import WholePlanEstimate
from .plan_analysis import area, PARSER_VERSION

FINISHES = ('tile', 'laminate', 'spc', 'parquet')


def decimal_text(value):
    return str(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def initial_rooms(analysis):
    rows = []
    for index, room in enumerate(analysis.rooms):
        explicit = room.get('finish') in FINISHES and bool(room.get('finish_evidence'))
        wet = room.get('kind') == 'bathroom'
        rows.append({**room, 'index': index, 'area': area(room.get('area')),
                     'finish': room['finish'] if explicit else ('tile' if wet else 'laminate'),
                     'finish_proposed': not explicit})
    return rows


def calculate_snapshot(rooms, analysis_id):
    book = PriceBook.objects.filter(is_active=True, published_at__isnull=False).first()
    output, grouped, procurement = [], {}, []
    for original in rooms:
        row = {k: original.get(k) for k in ('index','name','area','source','page','evidence','visual_evidence','finish','finish_proposed','finish_evidence')}
        row['area'] = area(row['area'])
        row['known'] = row['area'] is not None and Decimal(row['area']) >= 1
        row.update(materials=[], subtotal=None)
        output.append(row)
        if row['known']:
            grouped.setdefault(row['finish'], []).append(row)
    for finish, members in grouped.items():
        total_area = sum(Decimal(r['area']) for r in members)
        slug = 'plitka-keramogranit' if finish == 'tile' else 'laminat-spc-parket'
        definition = CALCULATORS_BY_SLUG[slug]
        inputs = {f['name']: str(f.get('default', '')) for f in definition['fields']}
        inputs['area'] = str(total_area)
        if finish == 'tile':
            inputs.update(zone='floor', tile_format='60x60', selected_variant='comfort')
        else:
            inputs['covering_type'] = finish
        result = calculate_materials(definition, inputs)
        quote = quotation(slug, 'comfort' if finish == 'tile' else '', result['materials'], book)
        priced = {(r['material_title'], r['unit_label']): r for r in quote['rows']} if quote else {}
        group_rows = []
        for material in result['materials']:
            if Decimal(str(material['quantity'])) <= 0:
                continue
            price = priced.get((material['title'], material['unit']))
            item = {'title': material['title'], 'unit': material['unit'],
                    'quantity': str(material['quantity']), 'unit_price': price['unit_price'] if price else None,
                    'line_total': price['line_total'] if price else None, 'finish': finish}
            group_rows.append(item)
            procurement.append(item)
        # Room rows are transparent proportional allocations of the grouped kit.
        # Purchase rounding happens once per finish, never once per room.
        for member in members:
            ratio = Decimal(member['area']) / total_area
            member['materials'] = [{**r, 'quantity': str((Decimal(r['quantity'])*ratio).quantize(Decimal('.0001'))),
                                    'line_total': decimal_text(Decimal(r['line_total'])*ratio) if r['line_total'] is not None else None}
                                   for r in group_rows]
            member['subtotal'] = decimal_text(sum(Decimal(r['line_total']) for r in member['materials'] if r['line_total'] is not None))
            member['allocation'] = 'area-share-of-grouped-kit'
    combined = {}
    for row in procurement:
        key = (row['title'], row['unit'], row['unit_price'])
        if key not in combined:
            combined[key] = {**row}
        else:
            combined[key]['quantity'] = str(Decimal(combined[key]['quantity']) + Decimal(row['quantity']))
            if row['line_total'] is not None:
                combined[key]['line_total'] = decimal_text(Decimal(combined[key]['line_total']) + Decimal(row['line_total']))
    procurement = list(combined.values())
    subtotal = decimal_text(sum(Decimal(r['line_total']) for r in procurement if r['line_total'] is not None))
    complete = bool(procurement) and all(r['unit_price'] is not None for r in procurement)
    unknown = sum(not r['known'] for r in output)
    return {'version': PARSER_VERSION, 'analysis_id': analysis_id, 'rooms': output, 'procurement': procurement,
            'known_area': decimal_text(sum(Decimal(r['area']) for r in output if r['known'])),
            'unknown_rooms': unknown, 'priced_subtotal': subtotal, 'prices_complete': complete,
            'materials_total': subtotal if complete else None,
            'total': None, 'work_total': None, 'scope': 'floor-materials-only',
            'rounding': 'grouped-by-finish', 'price_version': book.version if book else None,
            'price_source': book.source_note if book else None}


@transaction.atomic
def persist_estimate(upload, rooms, analysis_id):
    lock_price_configuration()
    snapshot = calculate_snapshot(rooms, analysis_id)
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    record, _ = WholePlanEstimate.objects.get_or_create(upload=upload, fingerprint=fingerprint, defaults={'snapshot': snapshot})
    summary = dict(upload.ai_summary or {})
    summary['whole_estimate_id'] = record.pk
    upload.ai_summary = summary
    upload.save(update_fields=['ai_summary'])
    return record
