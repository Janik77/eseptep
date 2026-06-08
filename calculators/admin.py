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
