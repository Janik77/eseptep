from django.contrib import admin

from .models import ProjectUpload, RenovationProject


@admin.register(RenovationProject)
class RenovationProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'customer_name', 'phone', 'area', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'customer_name', 'phone')


@admin.register(ProjectUpload)
class ProjectUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'repair_level', 'ai_status', 'area', 'created_at')
    list_filter = ('ai_status', 'repair_level', 'created_at')
    search_fields = ('user__username', 'comment', 'file')
    readonly_fields = ('created_at',)
