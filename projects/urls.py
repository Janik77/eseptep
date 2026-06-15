from django.urls import path

from .views import project_upload, projects_home

app_name = 'projects'

urlpatterns = [
    path('', projects_home, name='home'),
    path('upload/', project_upload, name='upload'),
]
