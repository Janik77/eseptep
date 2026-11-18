from django.urls import path

from .views import project_upload, projects_home, project_download

app_name = 'projects'

urlpatterns = [
    path('<int:pk>/download/', project_download, name='download'),
    path('', projects_home, name='home'),
    path('upload/', project_upload, name='upload'),
]

from .plan_views import plan_review, plan_image
urlpatterns += [
    path('<int:pk>/plan/', plan_review, name='plan_review'),
    path('<int:pk>/plan/page/<int:page>/', plan_image, name='plan_image'),
]

from .demo_samples import choose_sample
urlpatterns += [path('examples/select/', choose_sample, name='choose_sample')]
