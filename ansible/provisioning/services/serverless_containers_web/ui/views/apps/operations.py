import os
import json
import urllib
import functools

from django.conf import settings

from ui.utils import DEFAULT_APP_VALUES, DEFAULT_LIMIT_VALUES, DEFAULT_RESOURCE_VALUES, DEFAULT_HDFS_VALUES, SUPPORTED_RESOURCES, SUPPORTED_FRAMEWORKS
from ui.background_tasks import register_task, remove_task_by_name, add_app_task, start_app_task, start_hadoop_app_task, remove_app_task, remove_containers_from_app
from ui.views.core.utils import getHostsNames, getLimits, getHostFreeDiskLoad, getScalerPollFreq, setStructureResourcesForm, setLimitsForm, getStructuresValuesLabels, compareStructureNames, retrieve_global_hdfs_app, getDataAndFilterByApp, getContainersFromApp, getAppFiles
from ui.views.apps.utils import getAppInfo, getContainerResourcesForApp, getContainerAssignationForApp, setStartAppForm, setRemoveContainersFromAppForm, setAddAppForm, checkAppUser


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

    # Pure optional parameters
    for f in ['app_jar']:
        app_files[f] = request.POST.get(f, "")

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

    ## Hadoop apps specific config
    if app_files["app_type"] == "hadoop_app":
        if request.POST.get("add_extra_framework", False) and "framework" in request.POST:
            ## An extra framework has been selected (e.g., Spark), we change the app_type to build the corresponding container image
            app_files["framework"] = request.POST["framework"]
            if app_files["framework"] == "spark": app_files["app_type"] = "spark_app"
        else:
            ## If no extra framework has been selected, we select Hadoop to differentiate hadoop apps when retrieving them later from the StateDB
            app_files["framework"] = "hadoop"

    put_field_data = {
        'app': {
            ## Regular app data
            'name': kwargs["structure_name"],
            'resources': {},
            'guard': False,
            'subtype': "application",
            #'files_dir': "{0}/{1}".format(app_files['app_dir'], app_files['files_dir']) if app_files['files_dir'] != "" else "",
            'install_script': "{0}/{1}".format(app_files['app_dir'], app_files['install_script']) if app_files['install_script'] != "" else "",
            'install_files': "{0}/{1}".format(app_files['app_dir'], app_files['install_files']) if app_files['install_files'] != "" else "",
            'runtime_files': "{0}/{1}".format(app_files['app_dir'], app_files['runtime_files']) if app_files['runtime_files'] != "" else "",
            'output_dir': "{0}/{1}".format(app_files['app_dir'], app_files['output_dir']) if app_files['output_dir'] != "" else "",
            'start_script': "{0}/{1}".format(app_files['app_dir'], app_files['start_script']) if app_files['start_script'] != "" else "",
            'stop_script': "{0}/{1}".format(app_files['app_dir'], app_files['stop_script']) if app_files['stop_script'] != "" else "",
            ## Hadoop app data
            'app_jar': "{0}/{1}".format(app_files['app_dir'], app_files['app_jar']) if "app_jar" in app_files and app_files['app_jar'] != "" else "",
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
                put_field_data['app']['resources'][resource]['weight'] = int(resource_weight)

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
    app_name = kwargs["structure_name"]
    # Get existing hosts
    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}

    hosts = getHostsNames(data_json)
    # # Data to test
    # for i in range(2,5):
    #     hosts.append(hosts[0].copy())
    #     hosts[i]['name'] = "host{}".format(i+1)
    #     hosts[i]['resources'] = hosts[0]['resources'].copy()
    #     for key in ['cpu', 'mem', 'disks']:
    #         hosts[i]['resources'][key] = hosts[0]['resources'][key].copy()
    #         if key == 'disks':
    #             j = 0
    #             for disk in hosts[0]['resources'][key]:
    #                 hosts[i]['resources'][key][j] = disk.copy()
    #                 j += 1
    # hosts[0]['resources']['disks'][0]['load'] = 1
    # hosts[0]['resources']['disks'][1]['load'] = 1

    app = getAppInfo(data_json, kwargs["structure_name"])
    app_limits = getLimits(kwargs["structure_name"])

    ## APP info
    app_files = {}
    if app.get('start_script', ""):
        app_files['app_dir'] = os.path.dirname(app['start_script'])
    else:
        return "Error: there is no start script for app {0}".format(kwargs["structure_name"])

    for f in ['install_script', 'runtime_files', 'output_dir', 'start_script', 'stop_script', 'app_jar', 'framework']:
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

    # Check if there is space for app
    free_resources = {}
    for resource in app_resources:
        if resource == 'disk_read' or resource == "disk_write":
            continue
        free_resources[resource] = 0
        for host in hosts:
            if resource in host['resources']:
                free_resources[resource] += host['resources'][resource]['free']

    space_left_for_app = True
    for resource in free_resources:
        if free_resources[resource] < app_resources[resource]['min'] - app_resources[resource]['current']:
            space_left_for_app = False

    ## TODO: replace/add disk load check for disk I/O bandwidth check
    # Check if there is enough free disk load (specially important for Hadoop apps)
    if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']:
        disk_load = number_of_containers
        free_disk_load = 0
        for host in hosts:
            free_disk_load += getHostFreeDiskLoad(host)

        if free_disk_load < disk_load: space_left_for_app = False

    if not space_left_for_app:
        error = "There is no space left for app {0}".format(app_name)
        return error

    ## App type
    app_type = "base"
    if app_files.get('framework', "") != "":
        if app_files['framework'] not in SUPPORTED_FRAMEWORKS:
            raise Exception("{0} framework not supported, currently supported frameworks: {1}".format(app_files['framework'], SUPPORTED_FRAMEWORKS))
        app_type = "{0}_app".format(app_files['framework'])
    elif app_files.get('install_script', "") != "":
        app_type = "generic_app"
    is_hadoop_app = app_type in ["hadoop_app", "spark_app"]

    ## ResourceManager/NameNode resources
    rm_maximum_cpu, rm_minimum_cpu, rm_cpu_boundary = 100, 100, 25
    rm_maximum_mem, rm_minimum_mem, rm_mem_boundary = 1024, 1024, 25
    rm_maximum_energy, rm_minimum_energy, rm_energy_boundary = 50, 50, 10 # This value is provisional (it has to be tested)
    if is_hadoop_app:
        app_resources['cpu']['max'] -= rm_maximum_cpu
        app_resources['cpu']['min'] -= rm_minimum_cpu
        app_resources['mem']['max'] -= rm_maximum_mem
        app_resources['mem']['min'] -= rm_minimum_mem
        if settings.PLATFORM_CONFIG['power_budgeting']:
            app_resources['energy']['max'] -= rm_maximum_energy
            app_resources['energy']['min'] -= rm_minimum_energy

    # Get resources for containers
    container_resources = getContainerResourcesForApp(number_of_containers, app_resources, app_limits, benevolence, is_hadoop_app)

    if is_hadoop_app:
        container_resources['rm-nn']['cpu_max'] = rm_maximum_cpu
        container_resources['rm-nn']['cpu_min'] = rm_minimum_cpu
        container_resources['rm-nn']['cpu_weight'] = DEFAULT_RESOURCE_VALUES['weight']
        container_resources['rm-nn']['cpu_boundary'] = rm_cpu_boundary
        container_resources['rm-nn']['cpu_boundary_type'] = "percentage_of_max"
        container_resources['rm-nn']['mem_max'] = rm_maximum_mem
        container_resources['rm-nn']['mem_min'] = rm_minimum_mem
        container_resources['rm-nn']['mem_weight'] = DEFAULT_RESOURCE_VALUES['weight']
        container_resources['rm-nn']['mem_boundary'] = rm_mem_boundary
        container_resources['rm-nn']['mem_boundary_type'] = "percentage_of_max"
        if settings.PLATFORM_CONFIG['power_budgeting']:
            container_resources['rm-nn']['energy_max'] = rm_maximum_energy
            container_resources['rm-nn']['energy_min'] = rm_minimum_energy
            container_resources['rm-nn']['energy_weight'] = DEFAULT_RESOURCE_VALUES['weight']
            container_resources['rm-nn']['energy_boundary'] = rm_energy_boundary
            container_resources['rm-nn']['energy_boundary_type'] = "percentage_of_max"

        number_of_containers += 1

    ## Container assignation to hosts
    assignation_policy = request.POST['assignation_policy']
    allow_oversubscription = request.POST.get('allow_oversubscription', False)
    new_containers, disk_assignation, error = getContainerAssignationForApp(assignation_policy, allow_oversubscription, hosts, number_of_containers, container_resources, app_name)
    if error != "":
        return error

    container_resources["regular"] = {x: str(y) for x, y in container_resources["regular"].items()}
    if "bigger" in container_resources:
        container_resources["irregular"] = {x: str(y) for x, y in container_resources["bigger"].items()}
    if "smaller" in container_resources:
        container_resources["irregular"] = {x: str(y) for x, y in container_resources["smaller"].items()}
    if "rm-nn" in container_resources:
        container_resources["rm-nn"] = {x: str(y) for x, y in container_resources["rm-nn"].items()}

    ## Get scaler polling frequency
    scaler_polling_freq = getScalerPollFreq()
    virtual_cluster = settings.PLATFORM_CONFIG['virtual_mode']

    if is_hadoop_app:
        global_hdfs_data = None
        if settings.PLATFORM_CONFIG['global_hdfs']:
            use_global_hdfs = False
            for condition in ['read_from_global', 'write_to_global']:
                if request.POST.get(condition, False):
                    use_global_hdfs = True
                    break

            if use_global_hdfs:
                global_hdfs_data = {}
                ## Add global Namenode
                apps = getApps(data_json)
                global_hdfs_app, namenode_container = retrieve_global_hdfs_app(apps)
                if not global_hdfs_app:
                    return "Global HDFS requested but not found"
                if not namenode_container:
                    return "Namenode not found in global HDFS"
                global_hdfs_data['namenode_container_name'] = namenode_container['name']
                global_hdfs_data['namenode_host'] = namenode_container['host']

                ## Get additional info (read/write data from/to hdfs)
                for condition, additional_info in [('read_from_global', ['global_input', 'local_output']),
                                                   ('write_to_global', ['local_input', 'global_output'])]:
                    if request.POST.get(condition, False):
                        for info in additional_info:
                            global_hdfs_data[info] = request.POST.get(info) if request.POST.get(info, "") != "" else DEFAULT_HDFS_VALUES[info]
                    else:
                        for info in additional_info:
                            global_hdfs_data[info] = ""

        task = start_hadoop_app_task.delay(url, app_name, app_files, new_containers, container_resources, disk_assignation, scaler_polling_freq, virtual_cluster, app_type, global_hdfs_data)
    else:
        task = start_app_task.delay(url, app_name, app_files, new_containers, container_resources, disk_assignation, scaler_polling_freq, app_type)

    print("Starting task with id {0}".format(task.id))
    register_task(task.id, "{0}_app_task".format(app_name))

    return error


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
            'app_jar': os.path.basename(request.POST['app_jar']) if 'app_jar' in request.POST else ""
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

    scaler_polling_freq = getScalerPollFreq()

    task = remove_containers_from_app.delay(url, container_list, app, app_files, scaler_polling_freq)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"remove_containers_from_app")

    error = ""
    return error