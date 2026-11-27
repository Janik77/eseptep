"""Append-only canonical IDs. Never regenerate/reassign keys when labels/order change."""
import json
from pathlib import Path
REGISTRY = json.loads(Path(__file__).with_name('material_registry.json').read_text(encoding='utf-8'))
BY_KEY = {row['key']: row for row in REGISTRY}
BY_PAIR = {(row['name'], row['unit']): row['key'] for row in REGISTRY}

def material_key(name, unit):
    # Unknown canonical output fails closed; translations are never used as keys.
    return BY_PAIR.get((name, unit))

def material_choices():
    return [(row['key'], f"{row['key']} · {row['name']} ({row['unit']})") for row in REGISTRY]


def variant_keys(calculator_slug):
    from .definitions import CALCULATORS_BY_SLUG
    from .services import calculate_base
    definition = CALCULATORS_BY_SLUG[calculator_slug]
    data = {field['name']: str(field.get('default', '')) for field in definition.get('fields', [])}
    result = calculate_base(definition, data)
    return {row['key'] for row in result.get('variants', [])} or {''}
