from django.contrib import admin

from .models import (
    Calculation,
    ClientProject,
    MasterProfile,
    MasterResponse,
    ServiceRequest,
    SupplierMaterial,
    SupplierProfile,
    SupplierResponse,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'city', 'created_at')
    list_filter = ('role', 'city')
    search_fields = ('user__username', 'user__email', 'phone', 'city')


@admin.register(ClientProject)
class ClientProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'city', 'area_m2', 'rooms', 'repair_segment', 'status', 'created_at')
    list_filter = ('repair_segment', 'status', 'city')
    search_fields = ('title', 'user__username', 'city')


@admin.register(Calculation)
class CalculationAdmin(admin.ModelAdmin):
    list_display = ('project', 'calculator_slug', 'area_m2', 'segment', 'grand_total', 'created_at')
    list_filter = ('segment', 'calculator_slug')
    search_fields = ('project__title', 'calculator_slug')


@admin.register(MasterProfile)
class MasterProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'city', 'specialization', 'experience_years', 'rating', 'is_available')
    list_filter = ('city', 'is_available')
    search_fields = ('full_name', 'specialization', 'city')


@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'city', 'address', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('company_name', 'city', 'address')


@admin.register(SupplierMaterial)
class SupplierMaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier', 'category', 'unit', 'price', 'stock_status')
    list_filter = ('category', 'stock_status')
    search_fields = ('name', 'supplier__company_name', 'category')


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'project', 'request_type', 'status', 'created_at')
    list_filter = ('request_type', 'status', 'created_at')
    search_fields = ('client__username', 'project__title')


@admin.register(MasterResponse)
class MasterResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'request', 'master', 'price_from', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('master__full_name', 'request__project__title')


@admin.register(SupplierResponse)
class SupplierResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'request', 'supplier', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('supplier__company_name', 'request__project__title')
