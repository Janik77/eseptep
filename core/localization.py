"""Presentation-only translation. Calculator keys, formulas and stored snapshots stay canonical."""
from copy import copy
from django.forms import BaseForm
from django.shortcuts import render as django_render
from django.utils.translation import gettext, get_language

SYSTEM_CONTEXT = {'calculator', 'calculators', 'form_fields', 'segments', 'result',
                  'form_errors', 'parameters', 'variant_label', 'ai_summary', 'estimate', 'feature_cards', 'packages', 'results'}
DISPLAY_KEYS = {'title', 'label', 'description', 'unit', 'summary', 'warning', 'error',
                'help_text', 'cta', 'eyebrow', 'object_type', 'status', 'sections', 'next_step', 'repair_level', 'placeholder', 'display_value', 'copy_text', 'whatsapp_text',
                'saved_list', 'variant_heading', 'selected_variant_label', 'variant_label', 'segment_label', 'note', 'subtitle', 'price_note', 'extra_label', 'duration', 'items', 'selected_variant_description'}

def system_text(value):
    if not isinstance(value, str):
        return value
    return gettext(value)

def system_tree(value, key=''):
    if isinstance(value, dict):
        translated = {k: system_tree(v, k) for k, v in value.items()}
        if 'metrics' in translated:
            for metric in translated['metrics']:
                metric['value'] = system_text(metric.get('value'))
        if translated.get('variants'):
            translated['variant_heading'] = ' / '.join(v['title'] for v in translated['variants'])
        return translated
    if isinstance(value, (list, tuple)):
        return [system_tree(v, key) for v in value]
    return system_text(value) if key in DISPLAY_KEYS or key == 'form_errors' else value

def localize_form(form):
    for field in form.fields.values():
        field.label = gettext(str(field.label)) if field.label else field.label
        field.help_text = gettext(str(field.help_text)) if field.help_text else field.help_text
        if hasattr(field, 'choices'):
            field.choices = [(key, gettext(str(label))) for key, label in field.choices]
    return form

def render(request, template_name, context=None, *args, **kwargs):
    context = dict(context or {})
    # Derived display metrics must not repeat the user's input fields or round
    # source measurements. This copy never changes calculations or saved JSON.
    if context.get('result') and context.get('form_fields'):
        result = dict(context['result'])
        labels = {field['label'] for field in context['form_fields']}
        if context.get('calculator', {}).get('slug') == 'nalivnoy-pol':
            labels.update({'Площадь пола', 'Толщина'})
        result['metrics'] = [dict(metric) for metric in result.get('metrics', [])
                             if metric['label'] not in labels
                             and metric['label'] != 'Площадь укладки']
        context['result'] = result
    for key in SYSTEM_CONTEXT:
        if key in context:
            context[key] = system_tree(context[key], key)
    if context.get('result') and context.get('calculator'):
        localize_result(context['result'], context['calculator'])
    for item in context.get('parameters', []):
        item['value'] = system_text(item.get('value'))
    for value in context.values():
        if isinstance(value, BaseForm):
            localize_form(value)
    # Copy model instance only: never mutate the persistence JSON or user title.
    if 'calculation' in context:
        calculation = copy(context['calculation'])
        calculation.result_data = system_tree(calculation.result_data)
        context['calculation'] = calculation
        if 'title' in context:
            context['title'] = system_text(context['title'])
    return django_render(request, template_name, context, *args, **kwargs)


def localize_result(result, calculator):
    """Format composite copy text from typed fields, never substring-replace sentences."""
    if get_language() != 'kk':
        return
    inputs = result.get('meta', {}).get('input', {})
    parts = []
    for field in calculator.get('fields', []):
        value = inputs.get(field['name'])
        if value is None:
            continue
        label = next((option['label'] for option in field.get('options', []) if option['value'] == value), value)
        parts.append(f"{field['label']}: {label} {field.get('unit', '')}".strip())
    result['summary'] = calculator['title'] + (' · ' + ' · '.join(parts) if parts else '')
    result['saved_list'] = '\n'.join(f"{i}. {row['title']} — {row['quantity']} {row['unit']}" for i, row in enumerate(result['materials'], 1))
    result['copy_text'] = 'ESEPTEP.KZ\n' + result['summary'] + '\n\n' + result['saved_list'] + '\n\n' + gettext('Список составлен через ESEPTEP.KZ')
    result['whatsapp_text'] = result['copy_text']
