"""
URL configuration for my_website project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('minecraft/', include('minecraft.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from .views import index

def robots_txt(request):
    lines = [
        "User-agent: GPTBot",
        "Disallow: /",
        "",
        "User-agent: ClaudeBot",
        "Disallow: /",
        "",
        "User-agent: Google-Extended",
        "Disallow: /",
        "",
        "User-agent: CCBot",
        "Disallow: /",
        "",
        "User-agent: Bytespider",
        "Disallow: /",
        "",
        "User-agent: Omgilibot",
        "Disallow: /",
        "",
        "User-agent: anthropic-ai",
        "Disallow: /",
        "",
        "User-agent: *",
        "Disallow:",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

urlpatterns = [
    path("", index, name='index'),
    path("", include('minecraft.urls')),
    path("admin/", admin.site.urls),
    path("bird_classifier/", include("bird_classifier.urls")),
    path("robots.txt", robots_txt),
]
