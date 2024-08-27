from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('results/', views.result, name='result')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)