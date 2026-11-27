"""Browser-only review, publish and restore workflow for calculator materials."""
import json
from decimal import Decimal
from itertools import product
from pathlib import Path

from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy

from .definitions import CALCULATORS_BY_SLUG
from .material_keys import BY_KEY, REGISTRY, material_key
from .material_recipes import (AREA, CONSUMPTION, COUNT, COVERAGE, FACTOR, FIXED, LAYER, LEGACY,
                               PACK_LENGTH, PACK_MASS_UNITS, WHOLE_PURCHASE_UNITS, apply, scope_key)
from .models import RecipeEdition
from .pricing import attach_quotation, lock_price_configuration
from .services import calculate_base
from .validation import InputValidationError, MAX_AREA, MAX_COUNT

CATALOG = json.loads(Path(__file__).with_name('recipe_catalog.json').read_text(encoding='utf-8'))
SALT = 'calculators.recipe-publish.v1'
MODE_LABELS = {
    LEGACY: gettext_lazy('Исходная формула'),
    COVERAGE: gettext_lazy('Покрытие одной упаковки'),
    AREA: gettext_lazy('Расход на площадь'),
    LAYER: gettext_lazy('Расход на площадь и толщину'),
    CONSUMPTION: gettext_lazy('Расход смеси с учётом массы мешка'),
    COUNT: gettext_lazy('Расход на единицу входного параметра'),
    PACK_LENGTH: gettext_lazy('Полная длина рулона'),
    FACTOR: gettext_lazy('Коэффициент к исходному количеству'),
    FIXED: gettext_lazy('Фиксированное количество на объект'),
}
COUNT_LABELS = {'rooms': gettext_lazy('комната'), 'count': gettext_lazy('дверь'),
                'bathrooms': gettext_lazy('санузел')}
VARIANT_LABELS = {'': gettext_lazy('Без варианта'), 'base': gettext_lazy('Базовый'),
                  'optimal': gettext_lazy('Оптимальный'), 'maximum': gettext_lazy('Максимальный'),
                  'economy': gettext_lazy('Эконом'), 'comfort': gettext_lazy('Комфорт'),
                  'business': gettext_lazy('Бизнес')}


class BrowserDecimal(forms.DecimalField):
    widget = forms.TextInput(attrs={'inputmode': 'decimal'})
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace(',', '.')
        return super().to_python(value)


def material_label(key):
    row = BY_KEY[key]
    return f"{_(row['name'])} · {_(row['unit'])}"


def _number(name, label, **kw):
    return BrowserDecimal(label=label, required=False, min_value=Decimal(str(kw.get('min_value', '0.0001'))),
                          max_value=kw.get('max_value', 1000), max_digits=12,
                          decimal_places=kw.get('decimal_places', 4))


class RuleForm(forms.Form):
    mode = forms.ChoiceField(label=gettext_lazy('Действующее правило расчёта'), choices=[])
    rate = _number('rate', gettext_lazy('Норма'))
    pack_mass = _number('pack_mass', gettext_lazy('Масса упаковки, кг'), max_value=1000)
    count_field = forms.ChoiceField(required=False, label=gettext_lazy('Входной параметр'), choices=[])
    reserve = _number('reserve', gettext_lazy('Дополнительный запас, %'), min_value=0, max_value=100)
    rounding = forms.ChoiceField(label=gettext_lazy('Округление'), choices=[
        ('native', gettext_lazy('По единице материала')), ('up', gettext_lazy('Вверх до целой единицы')),
        ('precision', gettext_lazy('До сотых')),])
    price = _number('price', gettext_lazy('Справочная цена'), max_value=1000000, decimal_places=2, min_value='0.01')
    replacement = forms.ChoiceField(required=False, label=gettext_lazy('Заменить материал'), choices=[])
    when = forms.ChoiceField(required=False, label=gettext_lazy('Ограничить типом работы / покрытия'), choices=[])
    disabled = forms.BooleanField(required=False, label=gettext_lazy('Отключить материал'))
    source = forms.CharField(label=gettext_lazy('Источник нормы или цены'), max_length=255,
                             help_text=gettext_lazy('Упаковка, техкарта или данные поставщика.'))

    def __init__(self, calc, key, *args, add=False, **kwargs):
        self.calc, self.key, self.add = calc, key, add
        super().__init__(*args, **kwargs)
        unit = BY_KEY[key]['unit']
        fields = {f['name']: f for f in calc['fields']}
        count_fields = [k for k in COUNT_LABELS if k in fields]
        modes = [FIXED] if add else [LEGACY, FACTOR, FIXED]
        if {'area','floor_area'} & fields.keys():
            modes.append(AREA)
            if unit in WHOLE_PURCHASE_UNITS and (BY_KEY[key]['name'].endswith('кг') or unit in PACK_MASS_UNITS | {'упак.', 'рулон', 'рулонов'}):
                modes.append(COVERAGE)
        if 'thickness' in fields:
            modes.append(LAYER)
            if unit in PACK_MASS_UNITS:
                modes.append(CONSUMPTION)
        if count_fields:
            modes.append(COUNT)
        if unit == 'м' and not add:
            modes.append(PACK_LENGTH)
        self.fields['mode'].choices = [(mode, MODE_LABELS[mode]) for mode in modes]
        self.fields['count_field'].choices = [('', '—')] + [(k, COUNT_LABELS[k]) for k in count_fields]
        self.fields['replacement'].choices = [('', gettext_lazy('Без замены'))] + [
            (r['key'], material_label(r['key'])) for r in REGISTRY if r['key'] != key and r['unit'] == unit]
        self.fields['when'].choices = [('', gettext_lazy('Все подходящие входные данные'))] + [
            (f"{field['name']}:{choice['value']}", f"{_(field['label'])} · {_(choice['label'])}")
            for field in fields.values() if field.get('type') == 'select' for choice in field['options']]
        if unit in WHOLE_PURCHASE_UNITS:
            self.fields['rounding'].choices = list(self.fields['rounding'].choices)[:2]
        if key == 'mat_0034' and calc['slug'] == 'nalivnoy-pol':
            self.fields['rate'].label = _('Площадь покрытия одной упаковки, м²')
            self.fields['price'].label = _('Цена за упаковку, ₸')
            self.fields['pack_mass'].initial = '10'
            self.fields['rate'].help_text = _('Используется с правилом «Покрытие одной упаковки». Общий расход делится на покрытие; закупка округляется вверх.')
        else:
            self.fields['price'].label = _('Цена за единицу «%(unit)s», ₸') % {'unit': _(unit)}
            self.fields['rate'].label = _('Норма (единица зависит от правила)')
        self.fields['rate'].widget.attrs['data-unit'] = _(unit)

    def clean(self):
        data = super().clean()
        mode = data.get('mode')
        if mode and mode != LEGACY and data.get('rate') is None:
            self.add_error('rate', _('Введите положительное значение нормы.'))
        if mode == CONSUMPTION and data.get('pack_mass') is None:
            self.add_error('pack_mass', _('Укажите массу одной упаковки.'))
        if mode == COUNT and not data.get('count_field'):
            self.add_error('count_field', _('Выберите входной параметр.'))
        if (self.add or data.get('replacement')) and data.get('price') is None:
            self.add_error('price', _('Для нового или заменённого материала нужна собственная цена.'))
        if self.add and data.get('disabled'):
            self.add_error('disabled', _('Нельзя одновременно добавить и отключить материал.'))
        return data

    def contract(self):
        data = self.cleaned_data
        keys = ('mode','count_field','rounding','replacement','disabled','source')
        when = data.get('when')
        return {**{k:data[k] for k in keys}, 'add': self.add,
                'when': dict([when.split(':', 1)]) if when else {},
                **{k:format(data[k], 'f') if data[k] is not None else ''
                   for k in ('rate','pack_mass','reserve','price')}}


def _default_values(definition):
    return {f['name']: str(f.get('default','')) for f in definition['fields']}


def _inputs(definition, post=None):
    defaults = _default_values(definition)
    return {k: post.get(f'input_{k}', v) if post is not None else v for k,v in defaults.items()}


def _test_fields(definition, inputs):
    return [{'name':f['name'], 'label':_(f['label']), 'value':inputs[f['name']],
             'options':[(str(o['value']), _(o['label'])) for o in f.get('options',[])]}
            for f in definition['fields']]


def _preview(entry, definition, inputs, rules):
    legacy = calculate_base(definition, inputs)
    prior = apply(entry.slug, definition, dict(legacy), entry.current_id or '', entry.current.rules if entry.current_id else {})
    proposed = apply(entry.slug, definition, dict(legacy), 'draft', rules)
    attach_quotation(entry.slug, prior)
    attach_quotation(entry.slug, proposed)
    variants = []
    before_set = prior.get('variants') or [dict(prior, key='', title=definition['title'], total=prior['grand_total'])]
    after_set = proposed.get('variants') or [dict(proposed, key='', title=definition['title'], total=proposed['grand_total'])]
    for before, after in zip(before_set, after_set):
        row_map = lambda result: {(r['title'], r['unit']):r for r in result['materials']}
        old, new = row_map(before), row_map(after)
        lines = [{'title':name, 'unit':unit, 'before':old.get((name,unit)), 'after':new.get((name,unit))}
                 for name, unit in sorted(old.keys() | new.keys()) if old.get((name,unit), {}).get('quantity') != new.get((name,unit), {}).get('quantity')
                 or old.get((name,unit), {}).get('reference_total') != new.get((name,unit), {}).get('reference_total')
                 or old.get((name,unit), {}).get('reference_price') != new.get((name,unit), {}).get('reference_price')]
        variants.append({'title':_(after['title']), 'lines':lines, 'before':before['total'], 'after':after['total']})
    stamp = {
        'scope':entry.slug, 'revision':entry.draft_revision, 'current':entry.current_id,
        'params':(legacy.get('parameter_snapshot') or {}).get('version'),
        'price_book':(prior.get('admin_quote') or {}).get('version'),
    }
    return variants, stamp


def _validate_bounds(entry, definition, rules):
    """Reject rules that overflow persistent estimates on supported controls."""
    if not rules:
        return
    fields = definition['fields']
    values = [(str(o['value']) for o in f['options']) if f.get('type') == 'select' else
              (str(f['default']), str(f.get('max', MAX_COUNT if f.get('step') == 1 else MAX_AREA)))
              for f in fields]
    for combination in product(*values):
        data = {field['name']: value for field, value in zip(fields, combination)}
        try:
            base = calculate_base(definition, data)
        except InputValidationError:
            continue
        apply(entry.slug, definition, base, 'draft', rules)


def _link(admin, entry, *, material=None, variant=''):
    base = reverse('admin:calculators_recipecalculator_change', args=[entry.pk], current_app=admin.admin_site.name)
    if material:
        from urllib.parse import urlencode
        return f"{base}?{urlencode({'material':material, 'variant':variant})}"
    return base


def editor(request, admin, entry):
    if not admin.has_change_permission(request, entry):
        raise PermissionDenied
    definition = CALCULATORS_BY_SLUG[entry.slug]
    catalog = CATALOG[entry.slug]
    inputs = _inputs(definition, request.POST if request.method == 'POST' else None)
    posted = request.POST if request.method == 'POST' else request.GET
    key, variant = posted.get('material', ''), posted.get('variant', '')
    handle = scope_key(variant, key)
    selected = key in BY_KEY and variant in catalog
    item = entry.draft.get(handle, {})
    adding = selected and key not in catalog[variant]
    initial = {'mode':'coverage' if entry.slug=='nalivnoy-pol' and key=='mat_0034' else LEGACY,
               'rounding':'native', 'reserve':'0',
               **item,
               'when': ':'.join(next(iter(item.get('when',{}).items()))) if item.get('when') else ''}
    form = None
    action = request.POST.get('action')
    error = None
    preview = None
    token = None
    reference = None
    existing = None
    if selected:
        form = RuleForm(definition, key, request.POST if action=='save' else None, initial=initial, add=adding)
        try:
            base = calculate_base(definition, inputs)
            group = next((v for v in base.get('variants',[]) if v['key']==variant), base)
            reference = next((r for r in group['materials'] if material_key(r['title'],r['unit'])==key), None)
            active = (entry.current.rules.get(handle) or {}) if entry.current_id else {}
            if active:
                old_result = apply(entry.slug, definition, base, entry.current_id, entry.current.rules)
                old_group = next((v for v in old_result.get('variants',[]) if v['key']==variant), old_result)
                output = active.get('replacement') or key
                existing = next((r for r in old_group['materials'] if material_key(r['title'],r['unit'])==output), None)
        except InputValidationError:
            pass

    if action in ('save', 'reset', 'publish'):
        try:
            with transaction.atomic():
                lock_price_configuration()
                entry.refresh_from_db()
                if str(entry.draft_revision) != request.POST.get('revision'):
                    raise ValidationError(_('Черновик изменился. Откройте его заново.'))
                if action in ('save','reset'):
                    if not selected:
                        raise ValidationError(_('Выберите материал.'))
                    if action=='save' and not form.is_valid():
                        raise ValidationError(_('Проверьте поля материала.'))
                    draft = dict(entry.draft)
                    if action=='save':
                        new = form.contract()
                        replacement = new.get('replacement')
                        output = replacement or key
                        if replacement in catalog[variant] or any(
                            scope != handle and scope.split(':', 1)[0] == variant
                            and not rule.get('disabled') and (rule.get('replacement') or scope.split(':', 1)[1]) == output
                            for scope, rule in draft.items()
                        ):
                            raise ValidationError(_('Такой материал уже есть в этом комплекте. Измените его существующую строку.'))
                        draft[handle] = new
                    else:
                        draft.pop(handle,None)
                    entry.draft = draft
                    entry.draft_revision += 1
                    entry.draft_author = request.user
                    entry.draft_updated_at = timezone.now()
                    entry.save(update_fields=['draft','draft_revision','draft_author','draft_updated_at'])
                    messages.success(request, _('Черновик сохранён. Проверьте расчёт перед публикацией.'))
                    return redirect(_link(admin,entry))
                signed = signing.loads(request.POST.get('token',''), salt=SALT, max_age=3600)
                rollback = signed.get('rollback')
                source = entry.editions.filter(pk=rollback).first() if rollback else None
                restored_rules = source.rules if source else {} if rollback == 0 else entry.draft
                comparison, current_stamp = _preview(entry, definition, signed['inputs'], restored_rules)
                if current_stamp != signed['stamp'] or request.user.pk != signed.get('editor'):
                    raise ValidationError(_('Настройки изменились. Проверьте расчёт ещё раз.'))
                _validate_bounds(entry, definition, restored_rules)
                new = RecipeEdition.objects.create(calculator=entry, rules=restored_rules, author=request.user,
                                                   author_label=request.user.get_username(), restored_from=source)
                entry.current = new
                entry.draft = restored_rules
                entry.draft_revision += 1
                entry.draft_author = request.user
                entry.draft_updated_at = timezone.now()
                entry.save(update_fields=['current','draft','draft_revision','draft_author','draft_updated_at'])
                messages.success(request, _('Настройки опубликованы. Сохранённые сметы не изменились.'))
                return redirect(_link(admin,entry))
        except (signing.BadSignature, KeyError):
            error = _('Сначала проверьте расчёт.')
        except ValidationError as exc:
            error = ' '.join(exc.messages)
        except InputValidationError as exc:
            error = str(exc)

    if action == 'preview':
        try:
            raw = request.POST.get('rollback','')
            rollback = int(raw) if raw else None
            source = entry.editions.filter(pk=rollback).first() if rollback else None
            if rollback and source is None:
                raise ValidationError(_('Публикация не найдена.'))
            rules = source.rules if source else {} if rollback == 0 else entry.draft
            preview, stamp = _preview(entry, definition, inputs, rules)
            token = signing.dumps({'stamp':stamp,'inputs':inputs,'rollback':rollback,'editor':request.user.pk}, salt=SALT, compress=True)
        except (ValidationError, ValueError) as exc:
            error = ' '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

    groups = []
    for v, keys in catalog.items():
        keys = sorted(set(keys) | {scoped.split(':',1)[1] for scoped in entry.draft if scoped.split(':',1)[0]==v},
                      key=material_label)
        groups.append({'variant':v,'label':VARIANT_LABELS[v],
                       'rows':[{'label':material_label(k),'url':_link(admin,entry,material=k,variant=v),
                                'draft':entry.draft.get(scope_key(v,k)),
                                'current':entry.current.rules.get(scope_key(v,k)) if entry.current_id else None}
                               for k in keys]})
    request.current_app = admin.admin_site.name
    return TemplateResponse(request, 'admin/calculators/recipecalculator/editor.html', {
        **admin.admin_site.each_context(request), 'title': _(entry.title), 'opts':admin.model._meta,
        'entry':entry, 'definition':definition, 'groups':groups, 'form':form, 'token':token,
        'reference':reference, 'configured_example':existing, 'target':material_label(key) if selected else '', 'material':key,
        'variant':variant, 'adding':adding, 'preview':preview, 'error':error,
        'active_rule': MODE_LABELS[(entry.current.rules.get(handle) or {}).get('mode', LEGACY)] if entry.current_id else MODE_LABELS[LEGACY],
        'is_primer': entry.slug == 'nalivnoy-pol' and key == 'mat_0034',
        'inputs':_test_fields(definition,inputs), 'modes':MODE_LABELS, 'history':entry.editions.all()[:20],
        'catalog_options':sorted(((r['key'],material_label(r['key'])) for r in REGISTRY), key=lambda x:x[1]),
        'catalog_variants':[(v,VARIANT_LABELS[v]) for v in catalog], 'return_url':_link(admin,entry),
        'pack_mass': item.get('pack_mass') or ('10' if key=='mat_0034' else None),
    })
