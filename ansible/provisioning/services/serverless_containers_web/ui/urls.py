from django.urls import path

from . import views

urlpatterns = [
    # Home
    path('', views.home.index, name='index'),
    # Containers
    path('containers', views.containers.containers, name='containers'),
    path('containers/<container_name>/switch', views.containers.containers_guard_switch, name='containers_guard_switch'),
    # Hosts
    path('hosts', views.hosts.hosts, name='hosts'),
    path('hosts/<container_name>/switch', views.hosts.hosts_guard_switch, name='hosts_guard_switch'),
    # Apps
    path('apps', views.apps.apps, name='apps'),
    path('apps/<structure_name>/switch', views.apps.apps_guard_switch, name='apps_guard_switch'),
    path('apps/<structure_name>/stop', views.apps.apps_stop_switch, name='apps_stop_switch'),
    # Users
    path('users', views.users.users, name='users'),
    path('users/<structure_name>/switch', views.users.users_guard_switch, name='users_guard_switch'),
    # Services
    path('services', views.services.services, name='services'),
    path('services/<service_name>/switch', views.services.service_switch, name='service_switch'),
    # Rules
    path('rules', views.rules.rules, name='rules'),
    path('rules/<rule_name>/switch', views.rules.rule_switch, name='rule_switch'),
    # HDFS
    path('hdfs', views.hdfs.hdfs, name='hdfs'),
    path('hdfs/manage_global_hdfs', views.hdfs.manage_global_hdfs, name='manage_global_hdfs'),
    # Common
    path('structure_detail=<structure_name>_<structure_type>', views.common.structure_detail, name='structure_detail'),
    path('alerts/remove/<alert_id>', views.common.remove_pending_task, name='remove_alert'),
]