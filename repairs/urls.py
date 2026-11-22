from django.urls import path
from . import views

app_name = 'repairs'
urlpatterns = [
    path('review/', views.review_queue, name='review_queue'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/action/', views.action, name='action'),
    path('photo/<uuid:photo_id>/', views.photo, name='photo'),
]
