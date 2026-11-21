from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Agreement, Delivery, Event, PilotCity, Problem, Repair, Stage, Terms, city_key


class PilotCityForm(forms.ModelForm):
    class Meta:
        model = PilotCity
        fields = ['name', 'enabled']

    def clean_name(self):
        name = self.cleaned_data['name']
        key = city_key(name)
        if not key or PilotCity.objects.filter(key=key).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_('Укажите уникальное название города.'))
        return name


@admin.register(PilotCity)
class PilotCityAdmin(admin.ModelAdmin):
    form = PilotCityForm
    list_display = ['name', 'enabled']

    def has_delete_permission(self, request, obj=None):
        return False


class RepairForm(forms.ModelForm):
    class Meta:
        model = Repair
        fields = ['project', 'city', 'enabled', 'reviewer', 'delivery_address']

    def clean(self):
        values = super().clean()
        project, city, reviewer = (values.get(x) for x in ('project', 'city', 'reviewer'))
        if project and city and city_key(project.city) != city.key:
            self.add_error('city', _('Город пилота должен совпадать с городом проекта.'))
        if reviewer and not (reviewer.is_active and getattr(getattr(reviewer, 'profile', None), 'role', None) == 'admin'):
            self.add_error('reviewer', _('Выберите активного ответственного ESEPTEP.'))
        return values


@admin.register(Repair)
class RepairAdmin(admin.ModelAdmin):
    form = RepairForm
    list_display = ['project', 'city', 'enabled', 'reviewer']
    list_filter = ['enabled', 'city']

    def get_readonly_fields(self, request, obj=None):
        return ['project'] if obj else []

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnly(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Reviewers use the bound, gated customer UI, not global admin records.
        return qs.none()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register([Agreement, Terms, Delivery, Stage, Problem, Event], ReadOnly)
