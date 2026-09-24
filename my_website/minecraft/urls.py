from django.urls import path
from . import views
from . import voices

urlpatterns = [
    path('minecraft/', views.portal, name='minecraft'),
    path('minecraft/voices.json', voices.voices_json, name='minecraft-voices'),
    path('minecraft/voices/unlock', voices.voices_unlock, name='minecraft-voices-unlock'),
    path('minecraft/voices/token.json', voices.voices_token, name='minecraft-voices-token'),
    path('minecraft/live.json', views.live_board, name='minecraft-live'),
    path('minecraft/chat.json', views.chat_feed, name='minecraft-chat'),
    path('minecraft/activity.json', views.activity_feed, name='minecraft-activity'),
    path('minecraft/history.json', views.history_feed, name='minecraft-history'),
    path('minecraft/tree.json', views.skill_tree, name='minecraft-tree'),
    path('minecraft/guide/', views.guide, name='minecraft-guide'),
]