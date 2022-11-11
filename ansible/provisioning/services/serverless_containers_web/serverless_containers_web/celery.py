import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "serverless_containers_web.settings")
app = Celery("serverless_containers_web")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
