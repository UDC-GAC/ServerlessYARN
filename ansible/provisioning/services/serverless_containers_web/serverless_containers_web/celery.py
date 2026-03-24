import os

from celery import Celery

from celery.signals import after_setup_logger
import logging

@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Update all handlers
    for handler in logger.handlers:
        handler.setFormatter(formatter)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "serverless_containers_web.settings")
app = Celery("serverless_containers_web")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
