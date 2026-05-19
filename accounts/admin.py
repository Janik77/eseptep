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
    list_filter = ('role', 'city', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone', 'city')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(ClientProject)
class ClientProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'city', 'area_m2', 'rooms', 'repair_segment', 'status', 'created_at')
    list_filter = ('repair_segment', 'status', 'city', 'created_at')
    search_fields = ('title', 'user__username', 'user__email', 'city')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(Calculation)
class CalculationAdmin(admin.ModelAdmin):
    list_display = ('project', 'calculator_slug', 'area_m2', 'segment', 'materials_total', 'works_total', 'grand_total', 'created_at')
    list_filter = ('segment', 'calculator_slug', 'created_at')
    search_fields = ('project__title', 'project__user__username', 'calculator_slug')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(MasterProfile)
class MasterProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user', 'city', 'specialization', 'experience_years', 'rating', 'is_available')
    list_filter = ('city', 'specialization', 'is_available')
    search_fields = ('full_name', 'user__username', 'user__email', 'specialization', 'city', 'whatsapp')
    ordering = ('full_name',)


@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'city', 'address', 'whatsapp', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('company_name', 'user__username', 'user__email', 'city', 'address', 'whatsapp')
    ordering = ('company_name',)


@admin.register(SupplierMaterial)
class SupplierMaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier', 'category', 'unit', 'price', 'stock_status', 'delivery_time')
    list_filter = ('category', 'stock_status', 'supplier__city')
    search_fields = ('name', 'supplier__company_name', 'category', 'supplier__city')
    ordering = ('name',)


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'project', 'request_type', 'status', 'created_at')
    list_filter = ('request_type', 'status', 'created_at')
    search_fields = ('client__username', 'client__email', 'project__title', 'comment')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(MasterResponse)
class MasterResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'request', 'master', 'price_from', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'master__city')
    search_fields = ('master__full_name', 'request__project__title', 'request__client__username', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(SupplierResponse)
class SupplierResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'request', 'supplier', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'supplier__city')
    search_fields = ('supplier__company_name', 'request__project__title', 'request__client__username', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
