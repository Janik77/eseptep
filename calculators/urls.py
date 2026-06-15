from django.urls import path

from .views import calculator_detail, calculators_home

app_name = 'calculators'

urlpatterns = [
    path('', calculators_home, name='home'),
    path('<slug:slug>/', calculator_detail, name='detail'),
]
