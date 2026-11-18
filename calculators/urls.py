from django.urls import path

from .views import calculator_detail, calculators_home

from .pdf import saved_pdf

app_name = 'calculators'

urlpatterns = [
    path('saved/<str:calculation_id>/pdf/', saved_pdf, name='saved_pdf'),
    path('', calculators_home, name='home'),
    path('<slug:slug>/', calculator_detail, name='detail'),
]
