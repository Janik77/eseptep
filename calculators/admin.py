from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import CalculatorCategory, CalculatorTemplate


@admin.register(CalculatorCategory)
class CalculatorCategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'description')


@admin.register(CalculatorTemplate)
class CalculatorTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'unit', 'is_active', 'updated_at')
    list_filter = ('category', 'is_active')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'description')


from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from .models import PriceBook, MaterialPrice, RecipeCalculator
from .pricing import lock_price_configuration


@admin.register(RecipeCalculator)
class RecipeCalculatorAdmin(admin.ModelAdmin):
    list_display = ('translated_title', 'current', 'draft_updated_at')
    list_select_related = ('current',)
    search_fields = ('title', 'slug')

    @admin.display(description=_('Название'), ordering='title')
    def translated_title(self, obj):
        from django.utils.translation import gettext
        return gettext(obj.title)

    def get_search_results(self, request, queryset, search_term):
        from django.utils.translation import gettext, get_language
        base, duplicates = super().get_search_results(request, queryset, search_term)
        if search_term and get_language() == 'kk':
            matches = [c['slug'] for c in CALCULATORS if search_term.casefold() in gettext(c['title']).casefold()]
            base |= queryset.filter(pk__in=matches)
        return base, duplicates

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from django.shortcuts import get_object_or_404
        from .admin_recipes import editor
        return editor(request, self, get_object_or_404(self.get_queryset(request), pk=object_id))


from django import forms
from .definitions import CALCULATORS

def translated_material_choices():
    from .material_keys import REGISTRY
    from django.utils.translation import gettext
    return [(row['key'], f"{row['key']} · {gettext(row['name'])} ({gettext(row['unit'])})") for row in REGISTRY]


class MaterialPriceForm(forms.ModelForm):
    material_key = forms.ChoiceField(choices=lambda: [('', _('Выберите материал'))] + [(key, label) for key, label in translated_material_choices()])
    calculator_slug = forms.ChoiceField(choices=lambda: [('', _('Выберите калькулятор'))] + [(c['slug'], _(c['title'])) for c in CALCULATORS])
    variant_key = forms.ChoiceField(required=False, choices=[('', _('Без варианта')), ('base', _('Базовый')), ('optimal', _('Оптимальный')), ('maximum', _('Максимальный')), ('economy', _('Эконом')), ('comfort', _('Комфорт')), ('business', _('Бизнес'))])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('material_key', 'calculator_slug', 'variant_key'):
            self.fields[name].label = MaterialPrice._meta.get_field(name).verbose_name
        self.fields['unit'].help_text = _('Укажите единицу точно как в выбранном материале. Мешки, кг, м и м² не взаимозаменяемы. Для цены за упаковку укажите её фактическое содержимое в той же единице.')
        self.fields['material_key'].help_text = _('Выберите устойчивый идентификатор из справочника. Совпадение названия не подтверждает техническую пригодность товара.')
        self.fields['price'].help_text = _('Цена в тенге за расчётную единицу или одну упаковку, согласно выбранной основе. Не итог строки.')
        self.fields['pack_coverage'].help_text = _('Укажите, сколько м² или м в упаковке по данным магазина. Если магазин продаёт вразвес, оставьте пустым. При оплате упаковками укажите площадь упаковки и основу цены из прайса.')

    class Meta:
        model = MaterialPrice
        fields = '__all__'


class MaterialPriceInline(admin.TabularInline):
    form = MaterialPriceForm
    model = MaterialPrice
    extra = 1

    def has_add_permission(self, request, obj=None):
        return not (obj and obj.published_at)

    def has_change_permission(self, request, obj=None):
        return not (obj and obj.published_at)

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.published_at)


@admin.register(PriceBook)
class PriceBookAdmin(admin.ModelAdmin):
    change_list_template = "admin/calculators/pricebook/change_list.html"
    def get_urls(self):
        from django.urls import path
        from .admin_price_import import import_view
        return [path('import-csv/', self.admin_site.admin_view(lambda request: import_view(request, self)),
                     name='calculators_pricebook_import_csv')] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        from .admin_price_import import can_import
        return super().changelist_view(request, {**(extra_context or {}), 'can_import_floor_prices':can_import(self, request)})

    list_display = ('store_name', 'version', 'price_date', 'is_active', 'published_at')
    inlines = [MaterialPriceInline]
    actions = ['activate', 'deactivate']
    readonly_fields = ('is_active', 'published_at')
    search_fields = ('version', 'source_note')
    list_filter = ('is_active', 'published_at')
    ordering = ('-pk',)
    fieldsets = (
        (_('Источник'), {'fields': ('store_name', 'version', 'price_date', 'source_note')}),
        (_('Публикация'), {'fields': ('is_active', 'published_at'), 'description': _('Сохранение создаёт черновик. Проверьте значения и выберите действие публикации в списке. Опубликованная редакция неизменяема; новая заменяет действующую, но не старые сметы.')}),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'source_note' in form.base_fields:
            form.base_fields['source_note'].help_text = _('Укажите документ, автора или прайс магазина, дату и ограничения применимости. Значение без подтверждения не является строительной нормой.')
        if 'version' in form.base_fields:
            form.base_fields['version'].help_text = _('Уникальное обозначение редакции, например store-2026-11-18-v2. Не переиспользуйте обозначение опубликованной версии.')
        return form

    def has_change_permission(self, request, obj=None):
        if obj and obj.published_at:
            return False
        return super().has_change_permission(request, obj)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == 'POST':
            # The same lock covers form validation, parent save and inline saves.
            # Re-read publication state only after acquiring the lock; a draft
            # form opened before publication must not mutate the published edition.
            with transaction.atomic():
                lock_price_configuration()
                current = self.get_object(request, object_id) if object_id else None
                if current and current.published_at:
                    raise PermissionDenied(_('Опубликованную редакцию нельзя изменить. Создайте новую версию.'))
                return super().changeform_view(request, object_id, form_url, extra_context)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.published_at:
            return ('store_name', 'version', 'source_note', 'price_date', 'is_active', 'published_at')
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.published_at) and super().has_delete_permission(request, obj)

    @admin.action(description=_('Опубликовать выбранный прайс (заменить действующий)'), permissions=['change'])
    def activate(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, _('Выберите ровно одну редакцию.'), level='ERROR')
            return
        with transaction.atomic():
            lock_price_configuration()
            book = queryset.select_for_update().get()
            if not book.entries.exists():
                self.message_user(request, _('Перед публикацией добавьте подтверждённые цены материалов.'), level='ERROR')
                return
            PriceBook.objects.filter(is_active=True).update(is_active=False)
            book.is_active = True
            book.published_at = book.published_at or timezone.now()
            book.save(update_fields=['is_active', 'published_at'])
        self.message_user(request, _('Прайс опубликован. Сохранённые сметы не изменились.'))

    @admin.action(description=_('Отключить выбранные редакции'), permissions=['change'])
    def deactivate(self, request, queryset):
        with transaction.atomic():
            lock_price_configuration()
            queryset.update(is_active=False)


from .models import RenovationRateEdition


@admin.register(RenovationRateEdition)
class RenovationRateEditionAdmin(PriceBookAdmin):
    """Inherit the tested POST/publication lock and immutable edition permissions."""
    list_display = ('version', 'effective_date', 'economy_rate', 'standard_rate', 'premium_rate', 'is_active', 'published_at')
    inlines = []
    fieldsets = (
        (_('Источник'), {'fields': ('version', 'effective_date', 'source_note')}),
        (_('Предварительные ставки ремонта'), {'fields': ('economy_rate', 'standard_rate', 'premium_rate'), 'description': _('Только предварительная оценка ремонта под ключ в ₸/м². Это не цены материалов магазина. Проверьте все три уровня на одинаковой площади перед публикацией.')}),
        (_('Публикация'), {'fields': ('is_active', 'published_at')}),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.published_at:
            return ('version', 'source_note', 'effective_date', 'economy_rate', 'standard_rate', 'premium_rate', 'is_active', 'published_at')
        return ('is_active', 'published_at')

    @admin.action(description=_('Опубликовать ставки ремонта, ₸/м²'), permissions=['change'])
    def activate(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, _('Выберите ровно одну редакцию.'), level='ERROR')
            return
        with transaction.atomic():
            lock_price_configuration()
            edition = queryset.select_for_update().get()
            if edition.effective_date > timezone.localdate():
                self.message_user(request, _('Редакцию с будущей датой пока нельзя опубликовать.'), level='ERROR')
                return
            edition.full_clean()
            RenovationRateEdition.objects.filter(is_active=True).update(is_active=False)
            edition.is_active = True
            edition.published_at = edition.published_at or timezone.now()
            edition.save(update_fields=['is_active', 'published_at'])
        self.message_user(request, _('Ставки ремонта опубликованы. Исторические расчёты не изменились.'))


from .models import SelfLevelMixEdition


@admin.register(SelfLevelMixEdition)
class SelfLevelMixEditionAdmin(PriceBookAdmin):
    fieldsets = (
        (_('Источник'), {'fields': ('version', 'source_date', 'source_note')}),
        (_('Параметр'), {'fields': ('consumption', 'unit'), 'description': _('Влияет только на основную смесь наливного пола. Проверка: площадь × толщина в см × расход / 25 кг, округление мешков вверх.')}),
        (_('Публикация'), {'fields': ('is_active', 'published_at')}),
    )
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'consumption' in form.base_fields:
            from django.utils.translation import gettext
            form.base_fields['consumption'].help_text = gettext('Единица: кг/(м²·см), мешок 25 кг. Если источник указан в кг/(м²·мм), перед вводом переведите значение ×10. Автоматической конверсии нет. Диапазон 0,01–99,99 технический, не нормативный.')
        return form

    list_display = ('version', 'consumption', 'unit', 'source_date', 'is_active', 'published_at')
    inlines = []

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.published_at:
            return ('version', 'source_note', 'source_date', 'consumption', 'unit', 'is_active', 'published_at')
        return ('unit', 'is_active', 'published_at')

    @admin.action(description=_('Опубликовать расход смеси, кг/(м²·см), мешок 25 кг'), permissions=['change'])
    def activate(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, _('Выберите ровно одну редакцию.'), level='ERROR')
            return
        with transaction.atomic():
            lock_price_configuration()
            edition = queryset.select_for_update().get()
            if edition.source_date > timezone.localdate():
                self.message_user(request, _('Нельзя опубликовать редакцию с будущей датой источника.'), level='ERROR')
                return
            edition.full_clean()
            SelfLevelMixEdition.objects.filter(is_active=True).update(is_active=False)
            edition.is_active = True
            edition.published_at = edition.published_at or timezone.now()
            edition.save(update_fields=['is_active', 'published_at'])
        self.message_user(request, _('Расход смеси опубликован. Проверьте применимость по документации материала.'))


from .models import DemolitionFilmEdition


@admin.register(DemolitionFilmEdition)
class DemolitionFilmEditionAdmin(PriceBookAdmin):
    fieldsets = (
        (_('Источник'), {'fields': ('version', 'source_date', 'source_note')}),
        (_('Параметр'), {'fields': ('consumption', 'unit'), 'description': _('Влияет только на площадь защитной плёнки в демонтаже. Проверка: площадь × коэффициент, округление м² вверх. Не метод расчёта по радиаторам и дверям.')}),
        (_('Публикация'), {'fields': ('is_active', 'published_at')}),
    )
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'consumption' in form.base_fields:
            from django.utils.translation import gettext
            form.base_fields['consumption'].help_text = gettext('Единица: м² плёнки на 1 м² площади демонтажа. Без пересчёта в рулоны. Диапазон 0,01–99,99 технический, не нормативный. Применимость к объекту требует проверки.')
        return form

    list_display = ('version', 'consumption', 'unit', 'source_date', 'is_active', 'published_at')
    inlines = []

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.published_at:
            return ('version', 'source_note', 'source_date', 'consumption', 'unit', 'is_active', 'published_at')
        return ('unit', 'is_active', 'published_at')

    @admin.action(description=_('Опубликовать коэффициент плёнки, м²/м²'), permissions=['change'])
    def activate(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, _('Выберите ровно одну редакцию.'), level='ERROR')
            return
        with transaction.atomic():
            lock_price_configuration()
            edition = queryset.select_for_update().get()
            if edition.source_date > timezone.localdate():
                self.message_user(request, _('Нельзя опубликовать редакцию с будущей датой источника.'), level='ERROR')
                return
            edition.full_clean()
            DemolitionFilmEdition.objects.filter(is_active=True).update(is_active=False)
            edition.is_active = True
            edition.published_at = edition.published_at or timezone.now()
            edition.save(update_fields=['is_active', 'published_at'])
        self.message_user(request, _('Коэффициент плёнки опубликован. Проверьте применимость к объекту.'))
