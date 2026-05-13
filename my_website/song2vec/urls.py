from django.urls import path
from . import views

urlpatterns = [
    path('',        views.index,       name='song2vec_index'),
    path('search/', views.search,      name='song2vec_search'),
    path('render/', views.render_song, name='song2vec_render'),
]
