from django.urls import path

from .views import calculators_home

app_name = 'calculators'

urlpatterns = [
    path('', calculators_home, name='home'),
]
