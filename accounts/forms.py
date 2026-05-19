from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import ClientProject, MasterProfile, MasterResponse, UserProfile


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label='Имя')
    phone = forms.CharField(max_length=32, label='Телефон')
    email = forms.EmailField(label='Email')
    role = forms.ChoiceField(
        choices=[
            (UserProfile.Role.CLIENT, 'Клиент'),
            (UserProfile.Role.MASTER, 'Мастер'),
            (UserProfile.Role.SUPPLIER, 'Поставщик'),
        ],
        label='Роль',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'phone', 'email', 'role', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Пользователь с таким email уже существует.')
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
            'title': 'Название проекта',
            'city': 'Город',
            'area_m2': 'Площадь, м²',
            'rooms': 'Комнаты',
            'repair_segment': 'Сегмент ремонта',
        }


class MasterProfileForm(forms.ModelForm):
    class Meta:
        model = MasterProfile
        fields = ('full_name', 'photo', 'city', 'specialization', 'experience_years', 'rating', 'is_available', 'whatsapp', 'description')
        labels = {
            'full_name': 'Имя',
            'photo': 'Фото',
            'city': 'Город',
            'specialization': 'Специализация',
            'experience_years': 'Опыт, лет',
            'rating': 'Рейтинг',
            'is_available': 'Свободен',
            'whatsapp': 'WhatsApp',
            'description': 'Описание',
        }


class MasterResponseForm(forms.ModelForm):
    class Meta:
        model = MasterResponse
        fields = ('price_from', 'message')
        labels = {'price_from': 'Цена от', 'message': 'Сообщение клиенту'}
