from django.urls import path

from .views import projects_home

app_name = 'projects'

urlpatterns = [
    path('', projects_home, name='home'),
]
