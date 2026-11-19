## Platform logic shared by the web interface (ui.views) and the Celery worker (ui.background)
# This package must not import from ui.views, ui.forms or ui.background: the Celery autoreload (services/celery/start.sh)
# watches this package, so the worker would not be restarted when code imported from elsewhere changes
