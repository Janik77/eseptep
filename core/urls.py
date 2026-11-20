from django.urls import path

from . import pwa
from .views import home

app_name = 'core'

urlpatterns = [
    path('', home, name='home'),
    path('install/', pwa.install, name='pwa_install'),
    path('manifest.webmanifest', pwa.manifest, name='pwa_manifest'),
    path('service-worker.js', pwa.worker, name='pwa_worker'),
]
