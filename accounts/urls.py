from django.urls import path

from .views import (
    AccountLoginView,
    AccountLogoutView,
    client_dashboard,
    client_project_create,
    master_dashboard,
    master_profile_edit,
    register_view,
    supplier_dashboard,
    supplier_material_create,
    supplier_profile_edit,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', register_view, name='register'),
    path('login/', AccountLoginView.as_view(), name='login'),
    path('logout/', AccountLogoutView.as_view(), name='logout'),
    path('dashboard/client/', client_dashboard, name='dashboard_client'),
    path('dashboard/client/projects/create/', client_project_create, name='client_project_create'),
    path('dashboard/master/', master_dashboard, name='dashboard_master'),
    path('dashboard/master/profile/', master_profile_edit, name='master_profile_edit'),
    path('dashboard/supplier/', supplier_dashboard, name='dashboard_supplier'),
    path('dashboard/supplier/profile/', supplier_profile_edit, name='supplier_profile_edit'),
    path('dashboard/supplier/materials/create/', supplier_material_create, name='supplier_material_create'),
]
