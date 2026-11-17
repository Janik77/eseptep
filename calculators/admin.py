from django.contrib import admin

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
from .models import PriceBook, MaterialPrice
from .pricing import lock_price_configuration


from django import forms
from .material_keys import material_choices
from .definitions import CALCULATORS

class MaterialPriceForm(forms.ModelForm):
    material_key = forms.ChoiceField(choices=lambda: [('', 'Select material')] + material_choices())
    calculator_slug = forms.ChoiceField(choices=[('', 'Select calculator')] + [(c['slug'], c['title']) for c in CALCULATORS])
    variant_key = forms.ChoiceField(required=False, choices=[('', 'No variant'), ('base', 'base'), ('optimal', 'optimal'), ('maximum', 'maximum'), ('economy', 'economy'), ('comfort', 'comfort'), ('business', 'business')])
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
    list_display = ('store_name', 'version', 'price_date', 'is_active', 'published_at')
    inlines = [MaterialPriceInline]
    actions = ['activate', 'deactivate']
    readonly_fields = ('is_active', 'published_at')

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
                    raise PermissionDenied('Published prices are immutable. Create a new edition.')
                return super().changeform_view(request, object_id, form_url, extra_context)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.published_at:
            return ('store_name', 'version', 'source_note', 'price_date', 'is_active', 'published_at')
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.published_at) and super().has_delete_permission(request, obj)

    @admin.action(description='Publish/activate one price edition (previous edition becomes inactive)', permissions=['change'])
    def activate(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Select exactly one edition.', level='ERROR')
            return
        with transaction.atomic():
            lock_price_configuration()
            book = queryset.select_for_update().get()
            if not book.entries.exists():
                self.message_user(request, 'Add real price entries before publication.', level='ERROR')
                return
            PriceBook.objects.filter(is_active=True).update(is_active=False)
            book.is_active = True
            book.published_at = book.published_at or timezone.now()
            book.save(update_fields=['is_active', 'published_at'])
        self.message_user(request, 'Price edition activated. Saved estimates remain unchanged.')

    @admin.action(description='Deactivate selected editions', permissions=['change'])
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

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.published_at:
            return ('version', 'source_note', 'effective_date', 'economy_rate', 'standard_rate', 'premium_rate', 'is_active', 'published_at')
        return ('is_active', 'published_at')

    @admin.action(description='Publish typed renovation rates (all three tiers, KZT/m²)', permissions=['change'])
    def activate(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Select exactly one edition.', level='ERROR')
            return
        with transaction.atomic():
            lock_price_configuration()
            edition = queryset.select_for_update().get()
            if edition.effective_date > timezone.localdate():
                self.message_user(request, 'A future edition cannot be activated yet.', level='ERROR')
                return
            edition.full_clean()
            RenovationRateEdition.objects.filter(is_active=True).update(is_active=False)
            edition.is_active = True
            edition.published_at = edition.published_at or timezone.now()
            edition.save(update_fields=['is_active', 'published_at'])
        self.message_user(request, 'Renovation rates activated. Historical snapshots remain unchanged.')


from .models import SelfLevelMixEdition


@admin.register(SelfLevelMixEdition)
class SelfLevelMixEditionAdmin(PriceBookAdmin):
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

    @admin.action(description='Publish one consumption edition: kg/(m²·cm), fixed 25 kg bag', permissions=['change'])
    def activate(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Select exactly one edition.', level='ERROR')
            return
        with transaction.atomic():
            lock_price_configuration()
            edition = queryset.select_for_update().get()
            if edition.source_date > timezone.localdate():
                self.message_user(request, 'A future source date cannot be activated.', level='ERROR')
                return
            edition.full_clean()
            SelfLevelMixEdition.objects.filter(is_active=True).update(is_active=False)
            edition.is_active = True
            edition.published_at = edition.published_at or timezone.now()
            edition.save(update_fields=['is_active', 'published_at'])
        self.message_user(request, 'Consumption edition activated. Verify applicability against product documentation.')


from .models import DemolitionFilmEdition


@admin.register(DemolitionFilmEdition)
class DemolitionFilmEditionAdmin(PriceBookAdmin):
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

    @admin.action(description='Publish one protective film ratio edition: m²/m²', permissions=['change'])
    def activate(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Select exactly one edition.', level='ERROR')
            return
        with transaction.atomic():
            lock_price_configuration()
            edition = queryset.select_for_update().get()
            if edition.source_date > timezone.localdate():
                self.message_user(request, 'A future source date cannot be activated.', level='ERROR')
                return
            edition.full_clean()
            DemolitionFilmEdition.objects.filter(is_active=True).update(is_active=False)
            edition.is_active = True
            edition.published_at = edition.published_at or timezone.now()
            edition.save(update_fields=['is_active', 'published_at'])
        self.message_user(request, 'Film ratio edition activated. Verify applicability to the project.')
