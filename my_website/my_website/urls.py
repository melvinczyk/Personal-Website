from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from .views import index

# AI crawlers are turned away; everything else may look around.
AI_CRAWLERS = ('GPTBot', 'ClaudeBot', 'Google-Extended', 'CCBot', 'Bytespider',
               'Omgilibot', 'anthropic-ai')
ROBOTS_TXT = ''.join(f'User-agent: {bot}\nDisallow: /\n\n' for bot in AI_CRAWLERS) \
    + 'User-agent: *\nDisallow:'


def robots_txt(request):
    return HttpResponse(ROBOTS_TXT, content_type='text/plain')


urlpatterns = [
    path('', index, name='index'),
    path('', include('minecraft.urls')),
    path('admin/', admin.site.urls),
    path('bird_classifier/', include('bird_classifier.urls')),
    path('song2vec/', include('song2vec.urls')),
    path('robots.txt', robots_txt),
]
