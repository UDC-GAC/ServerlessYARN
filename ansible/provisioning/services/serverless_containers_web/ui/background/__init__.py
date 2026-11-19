## Celery tasks run by the worker (tasks.py), registered in serverless_containers_web/celery.py
# The platform logic used by the tasks lives in ui.domain. Do not import from ui.views or ui.forms here: the Celery autoreload
# (services/celery/start.sh) only watches ui.background and ui.domain, so changes in code imported from elsewhere would not restart the worker
