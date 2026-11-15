from django.utils.translation import gettext_lazy as _
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import (
    ClientProject,
    MasterProfile,
    MasterResponse,
    SupplierMaterial,
    SupplierProfile,
    SupplierResponse,
    UserProfile,
)


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label=_('Имя'))
    phone = forms.CharField(max_length=32, label=_('Телефон'))
    email = forms.EmailField(label='Email')
    role = forms.ChoiceField(
        choices=[
            (UserProfile.Role.CLIENT, _('Клиент')),
            (UserProfile.Role.MASTER, _('Мастер')),
            (UserProfile.Role.SUPPLIER, _('Поставщик')),
        ],
        label=_('Роль'),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'phone', 'email', 'role', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_('Пользователь с таким email уже существует.'))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email'].lower()
        user.email = self.cleaned_data['email'].lower()
        user.first_name = self.cleaned_data['first_name']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                phone=self.cleaned_data['phone'],
            )
        return user


class EseptepAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label='Email')


class ClientProjectCreateForm(forms.ModelForm):
    class Meta:
        model = ClientProject
        fields = ('title', 'city', 'area_m2', 'rooms', 'repair_segment')
        labels = {
            'title': _('Название проекта'),
            'city': _('Город'),
            'area_m2': _('Площадь, м²'),
            'rooms': _('Комнаты'),
            'repair_segment': _('Сегмент ремонта'),
        }


class MasterProfileForm(forms.ModelForm):
    class Meta:
        model = MasterProfile
        fields = ('full_name', 'photo', 'city', 'specialization', 'experience_years', 'is_available', 'whatsapp', 'description')


class MasterResponseForm(forms.ModelForm):
    price_from = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2, label=_("Цена от"))
    class Meta:
        model = MasterResponse
        fields = ('price_from', 'message')
        labels = {'price_from': _('Цена от'), 'message': _('Сообщение клиенту')}


class SupplierProfileForm(forms.ModelForm):
    class Meta:
        model = SupplierProfile
        fields = ('company_name', 'city', 'address', 'delivery_info', 'whatsapp', 'description', 'is_active')
        labels = {
            'company_name': _('Название компании'),
            'city': _('Город'),
            'address': _('Адрес'),
            'delivery_info': _('Доставка'),
            'whatsapp': 'WhatsApp',
            'description': _('Описание'),
            'is_active': _('Активный профиль'),
        }


class SupplierMaterialForm(forms.ModelForm):
    price = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2, label=_("Цена"))
    class Meta:
        model = SupplierMaterial
        fields = ('name', 'category', 'unit', 'price', 'stock_status', 'delivery_time')


class SupplierResponseForm(forms.ModelForm):
    total_price = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2, label=_("Итоговая цена"))
    delivery_time = forms.CharField(label=_('Срок поставки'), required=False)

    class Meta:
        model = SupplierResponse
        fields = ('total_price', 'message')
        labels = {'total_price': _('Итоговая цена'), 'message': _('Сообщение')}
