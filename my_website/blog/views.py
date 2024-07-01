from django.urls import path
from django.shortcuts import render

from . import views

def index(request):
	return render(request, 'templates/blog.html')
