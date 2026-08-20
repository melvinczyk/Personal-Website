from django.urls import path
from . import views

urlpatterns = [
    path('minecraft/', views.portal, name='minecraft'),
]