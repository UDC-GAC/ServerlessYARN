## Code run by the Celery worker (tasks and the helpers they use)
# Keep this package independent from Django-only code (e.g., ui.views, ui.forms): the Celery autoreload
# (services/celery/start.sh) only watches this package, so code imported from elsewhere would not trigger a restart
