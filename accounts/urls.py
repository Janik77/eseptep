from django.urls import path

from .views import (
    AccountLoginView,
    client_dashboard,
    calculation_detail,
    supplier_request_preview,
    supplier_request_detail,
    client_project_create,
    master_dashboard,
    master_profile_edit,
    logout_view,
    register_view,
    supplier_dashboard,
    supplier_material_create,
    supplier_profile_edit,
)

from .ai_views import explain_estimate

app_name = 'accounts'

urlpatterns = [
    path('calculations/<int:calculation_id>/explain/', explain_estimate, name='explain_estimate'),
    path('calculations/<int:calculation_id>/request-offer/', supplier_request_preview, name='supplier_request_preview'),
    path('requests/<int:request_id>/', supplier_request_detail, name='supplier_request_detail'),
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

from . import whole_views, whole_guest, turnkey_views
urlpatterns += [
    path('turnkey/preview/',turnkey_views.preview,name='turnkey_preview'),
    path('turnkey/<int:pk>/',turnkey_views.receipt,name='turnkey_request'),
    path('turnkey/<int:pk>/reply/',turnkey_views.reply,name='turnkey_reply'),
    path('whole/save/<int:estimate_id>/',whole_views.save_whole,name='save_whole'),
    path('whole/guest-save/<int:estimate_id>/',whole_guest.guest_save,name='whole_guest_save'),
    path('whole/<int:pk>/',whole_views.whole_saved,name='whole_saved'),
    path('whole/<int:pk>/request/',whole_views.whole_preview,name='whole_preview'),
    path('whole/<int:pk>/pdf/',whole_views.saved_whole_pdf,name='saved_whole_pdf'),
    path('whole-requests/<int:pk>/',whole_views.whole_request,name='whole_request'),
    path('whole-requests/<int:pk>/pdf/',whole_views.whole_offer_pdf,name='whole_offer_pdf'),
]
