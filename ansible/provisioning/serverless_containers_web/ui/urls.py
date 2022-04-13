from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('structures', views.structures, name='structures'),
    path('structure_detail=<structure_name>', views.structure_detail, name='structure_detail'),
    path('containers', views.containers, name='containers'),
    path('hosts', views.hosts, name='hosts'),
    path('apps', views.apps, name='apps'),
    path('services', views.services, name='services'),
    path('rules', views.rules, name='rules'),
]

