from django.urls import path

from .views import (
    AccountLoginView,
    client_dashboard,
    calculation_detail,
    client_project_create,
    master_dashboard,
    master_profile_edit,
    logout_view,
    register_view,
    supplier_dashboard,
    supplier_material_create,
    supplier_profile_edit,
)

app_name = 'accounts'

urlpatterns = [
    path('calculations/<str:calculation_id>/', calculation_detail, name='calculation_detail'),
    path('register/', register_view, name='register'),
    path('login/', AccountLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/client/', client_dashboard, name='dashboard_client'),
    path('dashboard/client/projects/create/', client_project_create, name='client_project_create'),
    path('dashboard/master/', master_dashboard, name='dashboard_master'),
    path('dashboard/master/profile/', master_profile_edit, name='master_profile_edit'),
    path('dashboard/supplier/', supplier_dashboard, name='dashboard_supplier'),
    path('dashboard/supplier/profile/', supplier_profile_edit, name='supplier_profile_edit'),
    path('dashboard/supplier/materials/<int:material_id>/edit/', supplier_material_create, name='supplier_material_edit'),
    path('dashboard/supplier/materials/create/', supplier_material_create, name='supplier_material_create'),
]
