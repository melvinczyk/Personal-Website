from django.urls import path
from . import views

urlpatterns = [
    path('minecraft/', views.portal, name='minecraft'),
    path('minecraft/live.json', views.live_board, name='minecraft-live'),
    path('minecraft/chat.json', views.chat_feed, name='minecraft-chat'),
    path('minecraft/guide/', views.guide, name='minecraft-guide'),
]