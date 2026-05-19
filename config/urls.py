from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import client_dashboard, client_project_create, master_dashboard, master_profile_edit

urlpatterns = [
    path('', include('core.urls')),
    path('calculators/', include('calculators.urls')),
    path('marketplace/', include('marketplace.urls')),
    path('projects/', include('projects.urls')),
    path('accounts/', include('accounts.urls')),
    path('dashboard/client/', client_dashboard, name='dashboard_client_root'),
    path('dashboard/client/projects/create/', client_project_create, name='dashboard_client_project_create_root'),
    path('dashboard/master/', master_dashboard, name='dashboard_master_root'),
    path('dashboard/master/profile/', master_profile_edit, name='dashboard_master_profile_root'),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
