# `ui` — ServerlessYARN web interface

Django app behind the ServerlessYARN web interface. The code is divided into three main layers:

- `views` handles HTTP requests.
- `background` holds the Celery tasks run by the worker.
- `domain` holds the platform logic that both of them use.

```
ui/
├── urls.py, forms.py, utils.py      # Django routes, forms and shared constants
├── views/                           # Presentation: request handling and page rendering (Django process)
├── background/                      # Celery tasks (Celery worker process)
├── domain/                          # Platform logic shared by views and background
├── templates/, templatetags/        # HTML templates and custom template tags
├── static/                          # CSS, JavaScript and images
├── old/                             # Deprecated code, kept for reference only (not imported anywhere)
└── admin.py, apps.py, models.py, migrations/, tests.py   # Django app boilerplate (no models are used)
```

## Dependency rules

```
views ──────► background ──────► domain
  │                                ▲
  └────────────────────────────────┘
```

- `views` may import from `background` (to queue tasks), `domain`, `forms` and `utils`.
- `background` may import only from `domain` and `utils`, never from `views` or `forms`.
- `domain` may import only from `utils`, never from `views`, `forms` or `background`.

These rules keep the code loaded by the Celery worker small and separate from the web interface. When the Celery autoreload is enabled (`celery_autoreload` in `config/modules/03-services.yml`), `services/celery/start.sh` watches only `background/`, `domain/` and `utils.py`, besides some files outside `ui`. If code in `background` or `domain` imported from `views` or `forms`, changes there would not restart the worker.

## Root files

| File | Content |
|---|---|
| `urls.py` | URL routes of every section, pointing to the functions exported by each `views/<section>` package |
| `forms.py` | All Django forms (crispy-forms) used by the views |
| `utils.py` | Constants and default values (e.g., `DEFAULT_APP_VALUES`, `DEFAULT_LIMIT_VALUES`, `SUPPORTED_RESOURCES`). It must not import from any other `ui` module, since both layers use it |

## `views/` — presentation

There is one package per section of the web interface: `home`, `containers`, `hosts`, `apps`, `users`, `services`, `rules`, `hdfs` and `common`. The `common` package covers pages and endpoints shared by sections, such as structure details, alerts and the apps API. Each package follows the same structure:

| File | Content |
|---|---|
| `__init__.py` | Re-exports the view functions referenced in `urls.py` |
| `views.py` | Django view functions: they receive the request, call the operations and render a template or redirect |
| `operations.py` | Processing of each form submission or GET request (`processAdd...`, `processRemove...`, `get...`), which usually queues Celery tasks |
| `utils.py` | Helpers tied to Django: building and filling forms, request/response helpers |

`views/core/` contains no views. It holds the logic shared by all sections:

- `core/operations.py` has `processStructures`, the generic GET/POST dispatcher used by the structure pages, and the operations shared by them (resources, limits, removal…).
- `core/utils.py` has the common form helpers (`setStructureResourcesForm`, `setLimitsForm`, `setRemoveStructureForm`) and request helpers (`redirect_with_errors`, `guard_switch`).

## `background/` — Celery tasks

| File | Content |
|---|---|
| `tasks.py` | Every `@shared_task` run by the worker, plus the helpers that register and track pending tasks shown as alerts in the interface |

Tasks are registered explicitly with `app.autodiscover_tasks(["ui.background"])` in `serverless_containers_web/celery.py`. Their names derive from the module path (`ui.background.tasks.<function>`), and external scripts use these names, e.g., `tests/power_budgeting/bin/app_management/run-app.py`. Renaming or moving a task changes its name.

Tasks should be thin wrappers that delegate the real work to `domain`. For example, `extend_lv_task` calls `domain.run_playbooks.extend_lv`, so the same logic can also run synchronously.

## `domain/` — platform logic

This package holds plain Python code with no Django views or forms. It may use `django.conf.settings` to read the platform configuration.

| File | Content |
|---|---|
| `state_db.py` | Access to the StateDatabase REST API (`getDbData`, `getDataAndFilterByApp`, `getLimits`, `getScalerPollFreq`, `checkAppUser`) |
| `structures.py` | Helpers over structures and apps (`getHostsNames`, `retrieve_app`, `retrieve_global_hdfs_app`, `getAppInfo`, `getContainersFromApp`, `getAppFiles`, `compareStructureNames`) |
| `placement.py` | Container placement: free resource checks (`getFreestHost`, `getFreestDisk`, `checkAvailableResources`…) and allocation policies (`assign_fill_up`, `assign_cyclic`, `assign_best_effort`, `assign_data_locality`…), selected through `getContainerAssignationForApp` |
| `container_resources.py` | Computation of container resources for an app (`getContainerResourcesForApp`) |
| `data_locality.py` | Per-host locality scores for the 'Data-locality' policy (from input block locations, a registry of previous deployments or the global HDFS datanodes) |
| `run_playbooks.py` | Wrappers that launch the Ansible playbooks (through `ansible_runner`) |
| `update_inventory_file.py` | Changes to the Ansible inventory (hosts, disks, containers) |

**NOTE**: `ansible/provisioning/scripts/load_apps_from_config.py` adds `ui` and `ui/domain` to `sys.path` and imports `utils` and `run_playbooks` directly, outside Django. Update the script if you rename or move either module.

## Where to put new code

- **A new page or form handler:** add it to the matching `views/<section>/` package (`views.py`, `operations.py`, `utils.py`) and add its route to `urls.py`.
- **Something slow that must run outside the request:** add a task to `background/tasks.py` and call it with `.delay()` from the views.
- **Logic needed by both views and tasks, or that has no reason to depend on Django forms:** put it in the `domain/` module for its responsibility, or create a new module there.
- **A constant or default value:** add it to `utils.py`.
