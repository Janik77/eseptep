from django.urls import path
from . import views

app_name = 'repairs'
urlpatterns = [
    path('review/', views.review_queue, name='review_queue'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/action/', views.action, name='action'),
    path('photo/<uuid:photo_id>/', views.photo, name='photo'),
]

from . import contract_views

urlpatterns += [
    path('<int:pk>/contracts/', contract_views.choose, name='contract_choose'),
    path('<int:pk>/contracts/<slug:kind>/', contract_views.show, name='contract_show'),
    path('<int:pk>/contracts/<slug:kind>/action/', contract_views.operate, name='contract_action'),
    path('<int:pk>/contracts/<slug:kind>/versions/<int:revision>.<str:extension>', contract_views.download, name='contract_download'),
    path('<int:pk>/contracts/<slug:kind>/original/<int:source>/', contract_views.original, name='contract_original'),
]
