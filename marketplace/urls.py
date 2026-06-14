from django.urls import path

from .views import marketplace_home

app_name = 'marketplace'

urlpatterns = [
    path('', marketplace_home, name='home'),
]
