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
