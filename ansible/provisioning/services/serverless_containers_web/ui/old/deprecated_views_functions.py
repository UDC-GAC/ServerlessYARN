from ui.forms import AddContainersForm, AddNContainersFormSetHelper, AddNContainersForm, AddContainersToAppForm
from ui.utils import BASE_URL, PLATFORM_CONFIG, DEFAULT_APP_VALUES, DEFAULT_LIMIT_VALUES, DEFAULT_RESOURCE_VALUES, DEFAULT_HDFS_VALUES, DEFAULT_SERVICE_PARAMETERS, request_to_state_db

from django.forms import formset_factory
import urllib.request
import urllib.parse
import json

from ui.background_tasks import start_containers_task_v2, add_host_task, add_app_task, start_app_on_container_task, add_disks_to_hosts_task
from ui.background_tasks import remove_container_task, remove_host_task, remove_app_task, remove_container_from_app_task, start_app_task, start_hadoop_app_task
from ui.background_tasks import register_task, get_pending_tasks_messages, remove_task, remove_containers_task, remove_containers_from_app

## Deprecated functions
## Not used ATM
def getAllContainers(data):
    containers = []

    for item in data:
        if (item['subtype'] == 'container'):
            containers.append(item)

    return containers

## Not used ATM
def getFreeContainers(allContainers, apps):
    freeContainers = []
    busyContainers = []

    for app in apps:
        busyContainers.extend(app['containers_full'])

    for container in allContainers:
        if container not in busyContainers:
            freeContainers.append(container)

    return freeContainers

## Not used ATM
def setAddContainersToAppForm(structure, free_containers, form_action):
    addContainersToAppForm = AddContainersToAppForm()
    addContainersToAppForm.fields['name'].initial = structure['name']
    addContainersToAppForm.fields['files_dir'].initial = structure['files_dir']
    addContainersToAppForm.fields['install_script'].initial = structure['install_script']
    addContainersToAppForm.fields['start_script'].initial = structure['start_script']
    addContainersToAppForm.fields['stop_script'].initial = structure['stop_script']

    addContainersToAppForm.helper.form_action = form_action

    # We can always use the formulary to add create containers for the app
    editable_data = 1
    # ATM, if a install_script is required we can't add existing containers because they may not have installed the app requirements
    if (structure['install_script'] == ""):
        for container in free_containers:
            editable_data += 1
            addContainersToAppForm.fields['containers_to_add'].choices.append(((container['name'],container['host']),container['name']))

    structure['add_containers_to_app_form'] = addContainersToAppForm
    structure['add_containers_to_app_editable_data'] = editable_data


## Not used ATM
def setAddNContainersForm(structures, hosts, form_action):

    form_initial_data_list = []
    editable_data = len(hosts)

    for host in hosts:
        form_initial_data = {'operation' : "add", 'structure_type' : "Ncontainers", 'host' : host['name'], 'containers_added': 0}
        form_initial_data_list.append(form_initial_data)

    formSet = formset_factory(AddNContainersForm, extra = 0)

    addNform = {}

    addNform['form'] = formSet(initial = form_initial_data_list)
    addNform['helper'] = AddNContainersFormSetHelper()
    addNform['helper'].form_action = form_action
    addNform['editable_data'] = editable_data

    #submit_button_disp = 4
    ## Need to do this to hide extra 'Save changes' buttons on JS
    #addNform['helper'].layout[submit_button_disp][0].name += structure['name']

    return addNform


## Not used ATM
def processFillWithNewContainers(request, url, app):

    # Calculate number of new containers based on all hosts free resources (CPU and mem ATM)
    newContainers = getNewPossibleContainers(url, app)

    # Start new containers (with app image if necessary) and start app on them
    app_files = {}
    app_files['files_dir'] = request.POST['files_dir']
    app_files['install_script'] = request.POST['install_script']
    app_files['start_script'] = request.POST['start_script']
    app_files['stop_script'] = request.POST['stop_script']

    for host in newContainers:
        task = start_containers_with_app_task.delay(url, host, newContainers[host], app, app_files)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id, "add_container_to_app_task")

    error = ""
    return error

## Not used ATM
def processAddHost_via_API(request, url, structure_name, structure_type, resources):

    full_url = url + structure_type + "/" + structure_name

    put_field_data = {
        'name': structure_name,
        'host': structure_name,
        'subtype': "host",
        'host_rescaler_ip': structure_name,
        'host_rescaler_port': 8000,
        'resources': {}
    }

    for resource in resources:
        if (resource + "_max" in request.POST):
            resource_max = request.POST[resource + "_max"]
            put_field_data['resources'][resource] = {'max': int(resource_max), 'free': int(resource_max)}

    error_message = "Error adding host {0}".format(structure_name)
    error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)

    return error

## Not used ATM
def processAddNContainers(request, url, host, containers_added):
    error = ""

    new_containers = {host: int(containers_added)}

    # start containers from playbook
    task = start_containers_task.delay(host, new_containers)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"start_containers_task")

    return error

## Not used ATM
def processAddContainerToApp(request, url, app, container_host_duple):

    cont_host = container_host_duple.strip("(").strip(")").split(',')
    container = cont_host[0].strip().strip("'")
    host = cont_host[1].strip().strip("'")

    app_files = {}
    app_files['files_dir'] = request.POST['files_dir']
    app_files['install_script'] = request.POST['install_script']
    app_files['start_script'] = request.POST['start_script']
    app_files['stop_script'] = request.POST['stop_script']

    full_url = url + "container/{0}/{1}".format(container,app)

    task = start_app_on_container_task.delay(full_url, host, container, app, app_files)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id, "start_app_on_container_task")

    error = ""
    return error

## Not used ATM
def getNewPossibleContainers(url, app_name):

    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}

    new_possible_containers = {}
    hosts = getHostsNames(data_json)
    app = getAppInfo(data_json,app_name)

    # free resources
    total_free_cpu = 0
    total_free_mem = 0
    for host in hosts:
        new_possible_containers[host['name']] = 0
        total_free_cpu += host['resources']['cpu']['free']
        total_free_mem += host['resources']['mem']['free']

    # CPU
    max_cpu_app = app['resources']['cpu']['max']
    min_cpu_app = app['resources']['cpu']['min']
    max_mem_app = app['resources']['mem']['max']
    min_mem_app = app['resources']['mem']['min']

    # TODO: read cpu values from config file OR app parameter (not added) OR get it somehow dinamically
    max_cpu_containers = 400
    min_cpu_containers = 50
    max_mem_containers = 4096
    min_mem_containers = 1024

    # CPU
    min_min_conts_app_cpu = int(min_cpu_app / min_cpu_containers) # minimum number of containers working at minimum considering app cpu resource
    max_min_conts_host_cpu = int(total_free_cpu / min_cpu_containers) # maximum number of containers working at minimum considering hosts cpu resource
    cpu_space_left = max_min_conts_host_cpu > min_min_conts_app_cpu # True there is space left for some containers considering cpu resource

    # MEM
    min_min_conts_app_mem = int(min_mem_app / min_mem_containers)
    max_min_conts_host_mem = int(total_free_mem / min_mem_containers)
    # TODO: fix free memory showing 0 on host
    #mem_space_left = max_min_conts_host_mem > min_min_conts_app_mem
    mem_space_left = True

    if (cpu_space_left and mem_space_left):

        remaining_max_cpu = max_cpu_app
        remaining_max_mem = max_mem_app

        for host in hosts:
            free_cpu = host['resources']['cpu']['free']
            free_mem = host['resources']['mem']['free']
            #max_containers_cpu[host['name']] = 0

            new_container_at_max_cpu = free_cpu >= max_cpu_containers and remaining_max_cpu > 0
            #new_container_at_max_mem = free_cpu >= max_mem_containers and remaining_max_mem > 0
            new_container_at_max_mem = True

            while new_container_at_max_cpu and new_container_at_max_mem:
                new_possible_containers[host['name']] += 1
                free_cpu -= max_cpu_containers
                free_mem -= max_mem_containers
                remaining_max_cpu -= max_cpu_containers
                remaining_max_mem -= max_mem_containers

                new_container_at_max_cpu = free_cpu >= max_cpu_containers and remaining_max_cpu > 0
                #new_container_at_max_mem = free_cpu >= max_mem_containers and remaining_max_mem > 0
                new_container_at_max_mem = True

            new_container_below_max_cpu = free_cpu >= min_cpu_containers and remaining_max_cpu > 0
            #new_container_below_max_mem = free_mem >= min_mem_containers and remaining_max_mem > 0
            new_container_below_max_mem = True

            if new_container_below_max_cpu and new_container_below_max_mem:
                new_possible_containers[host['name']] += 1
                remaining_max_cpu -= free_cpu
                remaining_max_mem -= free_mem
                free_cpu = 0
                free_mem = 0

                new_container_below_max_cpu = free_cpu >= min_cpu_containers and remaining_max_cpu > 0
                #new_container_below_max_mem = free_mem >= min_mem_containers and remaining_max_mem > 0
                new_container_below_max_mem = True

    return new_possible_containers


## Not used ATM
def processRemoveStructure_sync(request, url, structure_name, structure_type):

    structure_type_url = ""

    if (structure_type == "containers"):
        structure_type_url = "container"
        cont_host = structure_name.strip("(").strip(")").split(',')
        structure_name = cont_host[0].strip().strip("'")
        host_name = cont_host[1].strip().strip("'")

    elif (structure_type == "hosts"):
        structure_type_url = "host"
        containerList = getContainersFromHost(url, structure_name)

        for container in containerList:
            processRemoveStructure(request, url, "(" + container + "," + structure_name + ")", "containers")

    elif (structure_type == "apps"): structure_type_url = "apps"

    full_url = url + structure_type_url + "/" + structure_name

    error_message = "Error removing structure {0}".format(structure_name)
    error, _ = request_to_state_db(full_url, "delete", error_message)

    ## stop container
    if (structure_type == "containers" and error == ""):

        rc = subprocess.Popen(["./ui/scripts/stop_container.sh", host_name, structure_name])
        rc.communicate()

        # update inventory file
        remove_container_from_host(structure_name,host_name)

    ## remove host
    elif (structure_type == "hosts" and error == ""):

        # stop node scaler service in host
        rc = subprocess.Popen(["./ui/scripts/stop_host_scaler.sh", structure_name])
        rc.communicate()

        # update inventory file
        remove_host(structure_name)

    return error

## Not used ATM
def processRemoveStructure(request, url, structure_name, structure_type):

    structure_type_url = ""

    if (structure_type == "containers"):
        structure_type_url = "container"
        cont_host = structure_name.strip("(").strip(")").split(',')
        structure_name = cont_host[0].strip().strip("'")
        host_name = cont_host[1].strip().strip("'")

        full_url = url + structure_type_url + "/" + structure_name

        task = remove_container_task.delay(full_url, host_name, structure_name)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"remove_container_task")

    elif (structure_type == "hosts"):
        structure_type_url = "host"
        containerList = getContainersFromHost(url, structure_name)

        for container in containerList:
            processRemoveStructure(request, url, "(" + container + "," + structure_name + ")", "containers")

        full_url = url + structure_type_url + "/" + structure_name

        task = remove_host_task.delay(full_url, structure_name)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"remove_host_task")

    elif (structure_type == "apps"):
        structure_type_url = "apps"
        containerList, app_files = getContainersFromApp(url, structure_name)

        task = remove_app_task.delay(url, structure_type_url, structure_name, containerList, app_files)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"remove_app_task")

    error = ""
    return error

## Not used ATM
def processRemoveContainerFromApp(url, container_host_duple, app, app_files):

    cont_host = container_host_duple.strip("(").strip(")").split(',')
    container_name = cont_host[0].strip().strip("'")
    host = cont_host[1].strip().strip("'")
    disk_path = cont_host[2].strip().strip("'")

    full_url = url + "container/{0}/{1}".format(container_name, app)

    task = remove_container_from_app_task.delay(full_url, host, container_name, disk_path , app, app_files, "")
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"remove_container_from_app_task")

    error = ""
    return error