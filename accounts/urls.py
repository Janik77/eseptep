from django.urls import path

from .views import (
    AccountLoginView,
    AccountLogoutView,
    client_dashboard,
    master_dashboard,
    register_view,
    supplier_dashboard,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', register_view, name='register'),
    path('login/', AccountLoginView.as_view(), name='login'),
    path('logout/', AccountLogoutView.as_view(), name='logout'),
    path('dashboard/client/', client_dashboard, name='dashboard_client'),
    path('dashboard/master/', master_dashboard, name='dashboard_master'),
    path('dashboard/supplier/', supplier_dashboard, name='dashboard_supplier'),
]
