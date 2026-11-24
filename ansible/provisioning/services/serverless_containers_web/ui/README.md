# `ui` — ServerlessYARN web interface

Django app behind the ServerlessYARN web interface. The code is divided into three main layers:

- `views` handles HTTP requests.
- `background` holds the Celery tasks run by the worker.
- `domain` holds the platform logic that both of them use.

Code specific to Big Data apps (Hadoop, Spark and HDFS) is kept apart from the generic code in `bigdata`, plus the Celery tasks in `background/bigdata_tasks.py`.

```
ui/
├── urls.py, forms.py, utils.py      # Django routes, forms and shared constants
├── views/                           # Presentation: request handling and page rendering (Django process)
├── background/                      # Celery tasks (Celery worker process)
├── domain/                          # Platform logic shared by views and background
├── bigdata/                         # Big Data (Hadoop / Spark / HDFS) specific logic and forms
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

`bigdata` is not a separate layer, but a slice that crosses the other ones. Its modules follow the rules of the layer they belong to:

- `bigdata/forms.py` belongs to the presentation layer. It may import from `forms`, and only `views` may import it.
- The other `bigdata` modules belong to the domain layer. They may import from `domain`, `utils` and each other, never from `views`, `forms` or `background`.

These rules keep the code loaded by the Celery worker small and separate from the web interface. When the Celery autoreload is enabled (`celery_autoreload` in `config/modules/03-services.yml`), `services/celery/start.sh` watches only the relevant files in `background/`, `domain/` and `bigdata/`, as well as `utils.py`, besides some files outside `ui`.

## Root files

| File | Content |
|---|---|
| `urls.py` | URL routes of every section, pointing to the functions exported by each `views/<section>` package |
| `forms.py` | Django forms (crispy-forms) used by the views. Big Data forms are in `bigdata/forms.py` |
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
| `tasks.py` | The generic `@shared_task`s run by the worker, plus the helpers that register and track pending tasks shown as alerts in the interface |
| `bigdata_tasks.py` | The Big Data `@shared_task`s: starting and stopping Hadoop apps and the global HDFS, HDFS file operations and global HDFS replication monitoring. They reuse the task tracking helpers from `tasks.py` |

Big Data tasks are kept in `background` instead of `bigdata`, so every task run by the worker lives in the same package.

Tasks are registered explicitly in `serverless_containers_web/celery.py`: `app.autodiscover_tasks(["ui.background"])` registers `tasks.py`, and `app.autodiscover_tasks(["ui.background"], related_name="bigdata_tasks")` registers `bigdata_tasks.py`. Task names derive from the module path (`ui.background.tasks.<function>` and `ui.background.bigdata_tasks.<function>`), and external scripts use these names, e.g., `tests/power_budgeting/bin/app_management/run-app.py`. Renaming or moving a task changes its name.

Tasks should be thin wrappers that delegate the real work to `domain`. For example, `extend_lv_task` calls `domain.run_playbooks.extend_lv`, so the same logic can also run synchronously.

## `domain/` — platform logic

This package holds plain Python code with no Django views or forms. It may use `django.conf.settings` to read the platform configuration.

| File | Content |
|---|---|
| `state_db.py` | Access to the StateDatabase REST API (`getDbData`, `getDataAndFilterByApp`, `getLimits`, `getScalerPollFreq`, `checkAppUser`) |
| `structures.py` | Helpers over structures and apps (`getHostsNames`, `retrieve_app`, `retrieve_global_hdfs_app`, `getAppInfo`, `getContainersFromApp`, `getAppFiles`, `compareStructureNames`) |
| `placement.py` | Container placement: free resource checks (`getFreestHost`, `getFreestDisk`, `checkAvailableResources`…) and allocation policies (`assign_fill_up`, `assign_cyclic`, `assign_best_effort`, `assign_data_locality`…), selected through `getContainerAssignationForApp` |
| `container_resources.py` | Computation of container resources for an app (`getContainerResourcesForApp`) |
| `run_playbooks.py` | Wrappers that launch the Ansible playbooks (through `ansible_runner`). The Big Data ones are in `bigdata/playbooks.py` |
| `update_inventory_file.py` | Changes to the Ansible inventory (hosts, disks, containers) |

**NOTE**: `ansible/provisioning/scripts/load_apps_from_config.py` adds `ui` and `ui/domain` to `sys.path` and imports `utils` and `run_playbooks` directly, outside Django. Update the script if you rename or move either module.

## `bigdata/` — Big Data (Hadoop / Spark / HDFS) code

This package holds the code needed only by Big Data apps (`hadoop_app` and `spark_app`) and the global HDFS. The generic code calls it at specific points, usually after checking `is_bigdata_app` or whether the global HDFS is enabled.

| File | Content |
|---|---|
| `__init__.py` | Shared constants (`SUPPORTED_FRAMEWORKS`, `DEFAULT_HDFS_VALUES`) and helpers (`is_bigdata_app`, which reads `bigdata_app_types` from `vars/bigdata.yml`, and `get_framework_app_type`) |
| `start.py` | Big Data steps when adding and starting apps, called from `views/apps/operations.py`: app type selection by framework, master container resources, global HDFS disk exclusion and data, and the 'Data-locality' policy check |
| `resources.py` | Resources of the Hadoop/YARN daemons in each container (`set_hadoop_resources`) |
| `playbooks.py` | Wrappers that launch the Big Data Ansible tasks (`ansible/provisioning/tasks/bigdata`): Hadoop cluster setup and stop, HDFS frontend, HDFS file operations, data transfers between global and local HDFS, replication and block locations |
| `data_locality.py` | Per-host locality scores for the 'Data-locality' policy (from input block locations, a registry of previous deployments or the global HDFS datanodes) |
| `forms.py` | Big Data forms (`AddHadoopAppForm` and the HDFS file forms) and `set_bigdata_start_app_form`, which adds the global HDFS options and the 'Data-locality' policy to the generic `StartAppForm` |

The Big Data Ansible variables (`vars/bigdata.yml`) are loaded in `serverless_containers_web/settings.py` into `settings.VARS_CONFIG`, along with `vars/main.yml`.

## Where to put new code

- **A new page or form handler:** add it to the matching `views/<section>/` package (`views.py`, `operations.py`, `utils.py`) and add its route to `urls.py`.
- **Something slow that must run outside the request:** add a task to `background/tasks.py` and call it with `.delay()` from the views.
- **Logic needed by both views and tasks, or that has no reason to depend on Django forms:** put it in the `domain/` module for its responsibility, or create a new module there.
- **A constant or default value:** add it to `utils.py`, or to `bigdata/__init__.py` if only Big Data code uses it.
- **Anything specific to Hadoop, Spark or HDFS:** put it in the matching `bigdata/` module (forms in `bigdata/forms.py`, tasks in `background/bigdata_tasks.py`), and call it from the generic code only where needed.
