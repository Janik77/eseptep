from django.contrib import admin

from .models import RenovationProject


@admin.register(RenovationProject)
class RenovationProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'customer_name', 'phone', 'area', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'customer_name', 'phone')
