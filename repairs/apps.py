from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RepairsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'repairs'
    verbose_name = _('Мой ремонт')
