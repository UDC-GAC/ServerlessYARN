import os
import functools

from django.conf import settings

from ui.utils import DEFAULT_APP_VALUES, DEFAULT_LIMIT_VALUES, DEFAULT_RESOURCE_VALUES, SUPPORTED_RESOURCES
from ui.background.tasks import register_task, remove_task_by_name, add_app_task, start_app_task, remove_app_task, remove_containers_from_app
from ui.domain.state_db import getLimits, getScalerPollFreq, getDbData, getDataAndFilterByApp, checkAppUser
from ui.views.core.utils import setStructureResourcesForm, setLimitsForm, getStructuresValuesLabels
from ui.domain.structures import getContainersFromApp, getAppFiles, compareStructureNames, getAppInfo
from ui.domain.container_resources import getContainerResourcesForApp
from ui.views.apps.utils import setStartAppForm, setRemoveContainersFromAppForm, setAddAppForm

## Big Data (Hadoop / Spark / HDFS) apps
from ui.bigdata import is_bigdata_app, get_framework_app_type
from ui.bigdata.start import (set_bigdata_app_files, add_global_hdfs_allocation_exclusions, reserve_master_container_resources,
                              set_master_container_resources, check_data_locality_policy, get_global_hdfs_data)
from ui.background.bigdata_tasks import start_hadoop_app_task

def getApps(data):
    apps = []
    for item in data:
        if item['subtype'] == 'application':
            containers = []
            for structure in data:
                if structure['subtype'] == 'container' and structure['name'] in item['containers']:
                    structure['limits'] = getLimits(structure['name'])

                    ## Container Resources Form
                    setStructureResourcesForm(structure,"apps")

                    ## Container Limits Form
                    setLimitsForm(structure,"apps")

                    ## Set labels for container values
                    structure['resources_values_labels'] = getStructuresValuesLabels(structure, 'resources')
                    structure['limits_values_labels'] = getStructuresValuesLabels(structure, 'limits')

                    containers.append(structure)

            item['containers_full'] = sorted(containers, key=functools.cmp_to_key(compareStructureNames))
            item['limits'] = getLimits(item['name'])

            ## App Resources Form
            setStructureResourcesForm(item,"apps")

            ## App Limits Form
            setLimitsForm(item,"apps")

            ## Start App or Add Containers to App Form
            started_app = len(containers) > 0
            setStartAppForm(item, "apps", started_app)

            ## App RemoveContainersFromApp Form
            setRemoveContainersFromAppForm(item, containers, "apps")

            ## Set labels for apps values
            item['resources_values_labels'] = getStructuresValuesLabels(item, 'resources')
            item['limits_values_labels'] = getStructuresValuesLabels(item, 'limits')

            apps.append(item)

    # allContainers = getAllContainers(data)
    # freeContainers = getFreeContainers(allContainers, apps)

    # for app in apps:
    #     ## App AddContainersToApp Form
    #     setAddContainersToAppForm(app, freeContainers, "apps")

    return apps, setAddAppForm()


def processAddApp(request, url, **kwargs):
    full_url = url + "apps/" + kwargs["structure_name"]

    user = request.POST.get('user', None)

    ## APP info
    app_files = {}
    # Mandatory fields
    if 'app_dir' in request.POST:
        app_files['app_dir'] = request.POST['app_dir']
    else:
        raise Exception("Missing mandatory parameter: {0}".format('app_dir'))

    # Optional parameters with default value
    for f in ['start_script', 'stop_script']:
        if request.POST.get(f, "") != "":
            app_files[f] = request.POST[f]
        else:
            app_files[f] = DEFAULT_APP_VALUES[f]

    # Additional files
    for condition, additional_file in [('add_install', 'install_script'), ('add_install_files', 'install_files'), ('add_runtime_files', 'runtime_files'), ('add_output_dir', 'output_dir')]:
        if request.POST.get(condition, False):
            if request.POST.get(additional_file, "") != "":
                app_files[additional_file] = request.POST[additional_file]
            else:
                app_files[additional_file] = DEFAULT_APP_VALUES[additional_file]
        else:
            app_files[additional_file] = ""

    # App type
    app_files["app_type"] = "base"
    if request.POST.get("app_type", "") != "":
        app_files["app_type"] = request.POST["app_type"]
    elif app_files.get("install_script", "") != "":
        app_files["app_type"] = "generic_app"

    ## Big Data apps specific config
    set_bigdata_app_files(request.POST, app_files)

    put_field_data = {
        'app': {
            ## Regular app data
            'name': kwargs["structure_name"],
            'resources': {},
            'guard': False,
            'subtype': "application",
            'install_script': "{0}/{1}".format(app_files['app_dir'], app_files['install_script']) if app_files['install_script'] != "" else "",
            'install_files': "{0}/{1}".format(app_files['app_dir'], app_files['install_files']) if app_files['install_files'] != "" else "",
            'runtime_files': "{0}/{1}".format(app_files['app_dir'], app_files['runtime_files']) if app_files['runtime_files'] != "" else "",
            'output_dir': "{0}/{1}".format(app_files['app_dir'], app_files['output_dir']) if app_files['output_dir'] != "" else "",
            'start_script': "{0}/{1}".format(app_files['app_dir'], app_files['start_script']) if app_files['start_script'] != "" else "",
            'stop_script': "{0}/{1}".format(app_files['app_dir'], app_files['stop_script']) if app_files['stop_script'] != "" else "",
            ## Hadoop app data
            'framework': app_files["framework"] if "framework" in app_files else ""
        },
        'limits': {'resources': {}}
    }

    for resource in SUPPORTED_RESOURCES:
        if resource + "_max" in request.POST:
            resource_max = int(request.POST[resource + "_max"])
            resource_min = int(request.POST[resource + "_min"])
            put_field_data['app']['resources'][resource] = {'max': resource_max, 'min': resource_min, 'guard': 'false'}

            if resource + "_weight" in request.POST:
                if request.POST[resource + "_weight"] != "":
                    resource_weight = request.POST[resource + "_weight"]
                else:
                    resource_weight = DEFAULT_RESOURCE_VALUES["weight"]
                put_field_data['app']['resources'][resource]['weight'] = float(resource_weight)

        if resource + "_boundary" in request.POST:
            if request.POST[resource + "_boundary"] != "":
                resource_boundary = request.POST[resource + "_boundary"]
                resource_boundary_type = request.POST[resource + "_boundary_type"]
            else:
                resource_boundary = DEFAULT_LIMIT_VALUES["boundary"]
                resource_boundary_type = DEFAULT_LIMIT_VALUES["boundary_type"]

            put_field_data['limits']['resources'][resource] = {'boundary': resource_boundary, 'boundary_type': resource_boundary_type}

    error = ""
    task = add_app_task.delay(full_url, put_field_data, kwargs["structure_name"], app_files, user)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id, "add_app_task")

    return error


def processStartApp(request, url, **kwargs):

    # Exclude specific resources from container allocation
    allocation_exclusions = {}

    ## Disk exclusions
    if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']:

        ## Exclude disk for global HDFS frontend data transfer
        add_global_hdfs_allocation_exclusions(allocation_exclusions)

    # App info
    data_json = getDbData(url)
    app_name = kwargs["structure_name"]
    app = getAppInfo(data_json, app_name)
    app_limits = getLimits(app_name)

    app_files = {}
    if app.get('start_script', ""):
        app_files['app_dir'] = os.path.dirname(app['start_script'])
    else:
        return "Error: there is no start script for app {0}".format(app_name)

    for f in ['install_script', 'runtime_files', 'output_dir', 'start_script', 'stop_script', 'framework']:
        app_files[f] = os.path.basename(app[f]) if f in app else ""

    app_resources = {}
    for resource in app['resources']:
        if resource == "disk": continue
        app_resources[resource] = {}
        app_resources[resource]['max'] = app['resources'][resource]['max']
        app_resources[resource]['current'] = app['resources'][resource].get('current', 0)
        app_resources[resource]['min'] = app['resources'][resource]['min']
        app_resources[resource]['weight'] = app['resources'][resource].get('weight', DEFAULT_RESOURCE_VALUES["weight"])

    ## Containers to create
    number_of_containers = int(request.POST['number_of_containers'])
    benevolence = int(request.POST['benevolence'])

    ## App type
    app_type = "base"
    if app_files.get('framework', "") != "":
        app_type = get_framework_app_type(app_files['framework'])
    elif app_files.get('install_script', "") != "":
        app_type = "generic_app"
    is_hadoop_app = is_bigdata_app(app_type)

    ## ResourceManager/NameNode resources
    if is_hadoop_app:
        master_container_resources = reserve_master_container_resources(app_resources)

    # Get resources for containers
    container_resources = getContainerResourcesForApp(number_of_containers, app_resources, app_limits, benevolence, is_hadoop_app)

    container_resources["regular"] = {x: str(y) for x, y in container_resources["regular"].items()}
    if "bigger" in container_resources:
        container_resources["irregular"] = {x: str(y) for x, y in container_resources["bigger"].items()}
    if "smaller" in container_resources:
        container_resources["irregular"] = {x: str(y) for x, y in container_resources["smaller"].items()}
    if "master" in container_resources:
        container_resources["master"] = {x: str(y) for x, y in container_resources["master"].items()}

    if is_hadoop_app:
        set_master_container_resources(container_resources, master_container_resources)
        number_of_containers += 1

    ## Container assignation to hosts
    assignation_policy = request.POST['assignation_policy']
    allow_oversubscription = request.POST.get('allow_oversubscription', False)

    error = check_data_locality_policy(assignation_policy, is_hadoop_app)
    if error: return error

    container_resources["regular"] = {x: str(y) for x, y in container_resources["regular"].items()}
    if "bigger" in container_resources:
        container_resources["irregular"] = {x: str(y) for x, y in container_resources["bigger"].items()}
    if "smaller" in container_resources:
        container_resources["irregular"] = {x: str(y) for x, y in container_resources["smaller"].items()}
    if "master" in container_resources:
        container_resources["master"] = {x: str(y) for x, y in container_resources["master"].items()}

    ## Get scaler polling frequency
    scaler_polling_freq = getScalerPollFreq()
    virtual_cluster = settings.PLATFORM_CONFIG['virtual_mode']

    ## Get app dependency
    dependencies = {}
    if "dependency_app" in request.POST and request.POST["dependency_app"] != '':
        dependencies["app"] = request.POST["dependency_app"]
        if "dependency_condition" in request.POST:
            dependencies["conditions"] = request.POST.getlist("dependency_condition", None)
        else:
            dependencies["conditions"] = ["stopped"] # default

    assignation_requirements = {
        'app_resources': app_resources,
        'assignation_policy': assignation_policy,
        'allow_oversubscription': allow_oversubscription,
        'number_of_containers': number_of_containers,
        'allocation_exclusions': allocation_exclusions
    }

    if is_hadoop_app:
        global_hdfs_data = None
        if settings.PLATFORM_CONFIG['global_hdfs']:
            apps, _ = getApps(data_json)
            global_hdfs_data, error = get_global_hdfs_data(request.POST, apps, assignation_policy, assignation_requirements)
            if error: return error

        task = start_hadoop_app_task.delay(assignation_requirements, url, app_name, app_files, container_resources, scaler_polling_freq, virtual_cluster, app_type, global_hdfs_data, dependencies)
    else:
        task = start_app_task.delay(assignation_requirements, url, app_name, app_files, container_resources, scaler_polling_freq, app_type, dependencies)

    print("Starting task with id {0}".format(task.id))
    register_task(task.id, "{0}_app_task".format(app_name))

    return ""


def processStopApp(url, structure_name):
    errors = []
    container_list = []
    data, app = getDataAndFilterByApp(url, structure_name)
    app_containers = getContainersFromApp(data, app)
    app_files = getAppFiles(app)
    for container in app_containers:
        disk_path = ""
        if 'disk' in container['resources']:
            disk_path = container['resources']['disk']['path']

        container_list.append("({0},{1},{2})".format(container['name'],container['host'], disk_path))

    # Remove start app task to avoid FAILED state
    remove_task_by_name("{0}_app_task".format(structure_name))

    # Remove containers from app
    kwargs = {"containers_removed": container_list, "app": structure_name, "app_files": app_files}
    error = processRemoveContainersFromApp(None, url, **kwargs)
    if len(error) > 0:
        errors.append(error)

    return errors


def processRemoveApps(request, url, **kwargs):
    structure_type_url = "apps"
    for app_name in kwargs["selected_structures"]:
        # Get structures data
        data, app = getDataAndFilterByApp(url, app_name)
        app_containers = getContainersFromApp(data, app)
        app_files = getAppFiles(app)
        user = checkAppUser(app_name)
        task = remove_app_task.delay(url, structure_type_url, app_name, app_containers, app_files, user)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id, "remove_app_task")


def processRemoveContainersFromApp(request, url, **kwargs):
    if request:
        container_host_duples = request.POST.getlist('containers_removed', None)
        app = request.POST['app']
        app_files = {
            'runtime_files': os.path.basename(request.POST['runtime_files']),
            'output_dir': os.path.basename(request.POST['output_dir']),
            'install_script': os.path.basename(request.POST['install_script']),
            'start_script': os.path.basename(request.POST['start_script']),
            'stop_script': os.path.basename(request.POST['stop_script']),
            'app_dir': os.path.dirname(request.POST['start_script']),
        }
    else:
        container_host_duples = kwargs["containers_removed"]
        app = kwargs["app"]
        app_files = kwargs["app_files"]

    container_list = []
    for cont_hosts in container_host_duples:
        cont_host = cont_hosts.strip("(").strip(")").split(',')
        container = cont_host[0].strip().strip("'")
        host = cont_host[1].strip().strip("'")
        disk_path = cont_host[2].strip().strip("'")

        container_list.append({'container_name': container, 'host': host, 'disk_path': disk_path})

    # When requested by the user, just some of the app containers may be removed, so its DNS entries must be kept
    # Otherwise, the whole app is being stopped (processStopApp)
    remove_dns_entries = request is None
    task = remove_containers_from_app.delay(url, container_list, app, app_files, remove_dns_entries)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"remove_containers_from_app")

    error = ""
    return error