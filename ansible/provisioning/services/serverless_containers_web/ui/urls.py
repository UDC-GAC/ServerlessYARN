from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('structure_detail=<structure_name>', views.structure_detail, name='structure_detail'),
    path('containers', views.containers, name='containers'),
    path('hosts', views.hosts, name='hosts'),
    path('apps', views.apps, name='apps'),
    path('containers/<container_name>/switch', views.containers_guard_switch, name='containers_guard_switch'),
    path('hosts/<container_name>/switch', views.hosts_guard_switch, name='hosts_guard_switch'),
    path('apps/<structure_name>/switch', views.apps_guard_switch, name='apps_guard_switch'),
    path('apps/<structure_name>/stop', views.apps_stop_switch, name='apps_stop_switch'),
    path('services', views.services, name='services'),
    path('services/<service_name>/switch', views.service_switch, name='service_switch'),
    path('rules', views.rules, name='rules'),
    path('rules/<rule_name>/switch', views.rule_switch, name='rule_switch')
]

