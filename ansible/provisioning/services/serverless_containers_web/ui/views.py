from django.shortcuts import render,redirect
from ui.forms import RuleForm, DBSnapshoterForm, GuardianForm, ScalerForm, StructuresSnapshoterForm, SanityCheckerForm, RefeederForm, ReBalancerForm, EnergyManagerForm, WattTrainerForm
from ui.forms import LimitsForm, StructureResourcesForm, StructureResourcesFormSetHelper, HostResourcesForm, HostResourcesFormSetHelper
from ui.forms import AddHostForm, AddAppForm, AddHadoopAppForm, StartAppForm, AddDisksToHostsForm
from ui.forms import AddContainersForm, AddNContainersFormSetHelper, AddNContainersForm, AddContainersToAppForm
from ui.forms import RemoveStructureForm, RemoveContainersFromAppForm
from ui.forms import DEFAULT_BOUNDARY_PERCENTAGE

from django.forms import formset_factory
from django.http import HttpResponse
import urllib.request
import urllib.parse
import os
import json
import requests
import time
import yaml
import re
import functools
from bs4 import BeautifulSoup

from ui.background_tasks import start_containers_task_v2, add_host_task, add_app_task, add_container_to_app_task, add_disks_to_hosts_task
from ui.background_tasks import remove_container_task, remove_host_task, remove_app_task, remove_container_from_app_task, start_app_task, start_hadoop_app_task
from ui.background_tasks import register_task, get_pendings_tasks_to_string, remove_containers, remove_containers_from_app

config_path = "../../config/config.yml"
with open(config_path, "r") as config_file:
    config = yaml.load(config_file, Loader=yaml.FullLoader)

base_url = "http://{0}:{1}".format(config['server_ip'],config['orchestrator_port'])

# TODO: set and get values from config
# TODO: set max loads more accurately
max_load_dict = {}
max_load_dict["HDD"] = 1
max_load_dict["SSD"] = 4
max_load_dict["LVM"] = 20

# DEFAULT_APP_VALUES = {
#     "app_name": "",
#     "app_jar": "",
#     "install_script": "{app_name}/install.sh",
#     "start_script": "{app_name}/start.sh",
#     "stop_script": "{app_name}/stop.sh",
#     "files_dir": "{app_name}/files_dir"
# }

DEFAULT_APP_VALUES = {
    "app_jar": "",
    "install_script": "install.sh",
    "start_script": "start.sh",
    "stop_script": "stop.sh",
    "files_dir": "files_dir"
}

## Auxiliary general methods
def redirect_with_errors(redirect_url, errors):

    red = redirect(redirect_url)
    if (len(errors) > 0):
        red['Location'] += '?errors=' + urllib.parse.quote(errors[0])

        i = 1
        while(i < len(errors)):
            red['Location'] += '&errors=' + urllib.parse.quote(errors[i])
            i += 1

    else:
        red['Location'] += '?success=' + "Requests were successful!"

    return red

## Home
def index(request):
    url = base_url + "/heartbeat"
    
    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.URLError:
        data_json = {"status": "down"}

    return render(request, 'index.html', {'data': data_json})
    

#### Structures
# Views
def structure_detail(request,structure_name):
    url = base_url + "/structure/" + structure_name

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    return HttpResponse(json.dumps(data_json), content_type="application/json")

def structures(request, structure_type, html_render):
    url = base_url + "/structure/"

    if (len(request.POST) > 0):
        errors = []

        resources_errors = processResources(request, url)
        limits_errors = processLimits(request, url)
        add_errors = processAdds(request, url)
        removes_errors = processRemoves(request, url, structure_type)

        if (resources_errors): errors += resources_errors
        if (limits_errors): errors += limits_errors
        if (add_errors): errors += add_errors
        if (removes_errors): errors += removes_errors

        return redirect_with_errors(structure_type,errors)

    requests_errors = request.GET.getlist("errors", None)
    requests_successes = request.GET.getlist("success", None)
    requests_info = []

    ## Pending tasks
    still_pending_tasks, successful_tasks, failed_tasks = get_pendings_tasks_to_string()
    requests_errors.extend(failed_tasks)
    requests_successes.extend(successful_tasks)
    requests_info.extend(still_pending_tasks)

    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}

    structures = []
    addStructureForm = None
    if (structure_type == "containers"):
        structures = getContainers(data_json)
        hosts = getHostsNames(data_json)
        addStructureForm = {}
        addStructureForm['add_containers'] = setAddContainersForm(structures,hosts,structure_type)
        #addStructureForm['add_n_containers'] = setAddNContainersForm(structures,hosts,structure_type)

    elif(structure_type == "hosts"):
        structures = getHosts(data_json)
        addStructureForm = {}
        addStructureForm['host'] = AddHostForm()
        addStructureForm['add_disks_to_hosts'] = setAddDisksToHostsForm(structures,structure_type)

    elif(structure_type == "apps"):
        structures = getApps(data_json)
        addStructureForm = {}
        addStructureForm['app'] = AddAppForm()
        addStructureForm['hadoop_app'] = AddHadoopAppForm()

    ## Set RemoveStructures Form
    removeStructuresForm = setRemoveStructureForm(structures, structure_type)

    context = {
        'data': structures,
        'requests_errors': requests_errors,
        'requests_successes': requests_successes,
        'requests_info': requests_info,
        'addStructureForm': addStructureForm,
        'removeStructuresForm': removeStructuresForm
    }

    return render(request, html_render, context)


def containers(request):
    return structures(request, "containers","containers.html")
    
def hosts(request):
    return structures(request, "hosts","hosts.html")

def apps(request):
    return structures(request, "apps","apps.html")

# Prepare data to HTML
def compareStructureNames(structure1, structure2):
    # When using a dict to store container info
    if isinstance(structure1, dict):
        cname1 = structure1['name']
        cname2 = structure2['name']
    # When using a tuple to store container info (host core mapping case))
    elif isinstance(structure1, tuple):
        cname1 = structure1[0]
        cname2 = structure2[0]
    # When using containers as strings
    else:
        cname1 = structure1
        cname2 = structure2

    id1 = re.sub('.*?([0-9]*)$',r'\1',cname1)
    id2 = re.sub('.*?([0-9]*)$',r'\1',cname2)

    if id1 != "" and id2 != "":
        basename1 = cname1[:-len(id1)]
        basename2 = cname2[:-len(id2)]
    else:
        basename1 = cname1
        basename2 = cname2

    if basename1 < basename2:
        return -1
    elif basename1 > basename2:
        return 1
    else:
        if id1 != "" and id2 != "":
            if int(id1) < int(id2):
                return -1
            elif int(id1) > int(id2):
                return 1
            else:
                return 0
        else:
            return 0

def getHosts(data):
    hosts = []

    for item in data:
        if (item['subtype'] == 'host'):
            containers = []
            for structure in data:
                if (structure['subtype'] == 'container' and structure['host'] == item['name']):
                    structure['limits'] = getLimits(structure['name'])

                    ## Container Resources Form
                    setStructureResourcesForm(structure,"hosts")

                    ## Container Limits Form
                    setLimitsForm(structure,"hosts")

                    ## Set labels for container values
                    structure['resources_values_labels'] = getStructuresValuesLabels(structure, 'resources')
                    structure['limits_values_labels'] = getStructuresValuesLabels(structure, 'limits') 

                    containers.append(structure)

            ## we order this list using name container to keep the order consistent with the 'cpu_cores' dict below
            item['containers'] = sorted(containers, key=functools.cmp_to_key(compareStructureNames))

            # Adjustment to don't let core_usage_mapping be too wide on html display
            if ("cpu" in item['resources'] and "core_usage_mapping" in item['resources']['cpu']):

                # Remove removed containers from host core mapping
                core_mapping = {}
                container_names = [d['name'] for d in item['containers']]
                for core, mapping in list(item['resources']['cpu']['core_usage_mapping'].items()):
                    m = {k:v for k,v in mapping.items() if k in container_names or k == "free"}
                    core_mapping[core] = m

                # Core sorting
                core_mapping = {int(k) : v for k, v in core_mapping.items()}
                core_mapping = dict(sorted(core_mapping.items()))

                ## fill usage with 0 when a container doesn't show in a core
                for core,mapping in list(core_mapping.items()):
                    for cont in item['containers']:
                        if (cont['name'] not in mapping):
                            mapping[cont['name']] = 0

                    mapping = dict(sorted(mapping.items(),key=functools.cmp_to_key(compareStructureNames)))

                    ## Move 'free' shares of core always to start of dict
                    free = mapping['free']
                    mapping_list = list(mapping.items())
                    mapping_list.remove(('free',free))
                    mapping_list.insert(0,('free',free))

                    core_mapping[core] = dict(mapping_list)

                item['resources']['cpu_cores'] = core_mapping

                # remove core_usage_mapping from the cpu resources since now that info is in 'cpu_cores'
                item['resources']['cpu'] = {k:v for k,v in item['resources']['cpu'].items() if k != 'core_usage_mapping'}

            ## Host Resources Form
            setStructureResourcesForm(item,"hosts")

            ## Set labels for host values
            item['resources_values_labels'] = getStructuresValuesLabels(item, 'resources')

            hosts.append(item)

    hosts = sorted(hosts,key=functools.cmp_to_key(compareStructureNames))
    return hosts

def getHostsNames(data):

    hosts = []

    for item in data:
        if (item['subtype'] == 'host'):

            hosts.append(item)

    hosts = sorted(hosts,key=functools.cmp_to_key(compareStructureNames))
    return hosts

def getApps(data):
    apps = []

    for item in data:
        if (item['subtype'] == 'application'):
            containers = []
            for structure in data:
                if (structure['subtype'] == 'container' and structure['name'] in item['containers']):
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

    return apps

def getContainers(data):
    containers = []

    for item in data:
        if (item['subtype'] == 'container'):
            item['limits'] = getLimits(item['name'])

            ## Container Resources Form
            setStructureResourcesForm(item,"containers")

            ## Container Limits Form
            setLimitsForm(item,"containers")

            ## Set labels for container values
            item['resources_values_labels'] = getStructuresValuesLabels(item, 'resources')
            item['limits_values_labels'] = getStructuresValuesLabels(item, 'limits')

            containers.append(item)
    return sorted(containers, key=functools.cmp_to_key(compareStructureNames))

def getAppInfo(data, app_name):
    app = {}

    for item in data:
        if (item['subtype'] == 'application' and item['name'] == app_name):

            return item

    return app

def getScalerPollFreq():

    scaler_polling_freq = 5

    url = base_url + "/service/scaler"

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())

    if 'config' in data_json and 'POLLING_FREQUENCY' in data_json['config']:
        scaler_polling_freq = data_json['config']['POLLING_FREQUENCY']

    return scaler_polling_freq

def getStructuresValuesLabels(item, field):

    values_labels = []

    if (field in item and len(list(item[field].keys())) > 0):
        first_key = list(item[field].keys())[0]

        if (first_key != 'cpu_cores'):
            values_labels = item[field][first_key]
        else:
            ## just in case we get 'cpu_cores' field from a host as first key
            values_labels = item[field]['cpu']

    return values_labels


def setStructureResourcesForm(structure, form_action):

    editable_data = 0

    full_resource_list = ["cpu","mem","disk","net","energy"]
    structures_resources_field_list = ["guard","max","min"]
    host_resources_field_list = ["max"]
    form_initial_data_list = []

    resource_list = []
    for resource in full_resource_list:
        if (resource in structure['resources']):
            resource_list.append(resource)

    if (structure['subtype'] == "host"):
        resources_field_list = host_resources_field_list
    else:
        resources_field_list = structures_resources_field_list

    for resource in resource_list:
        form_initial_data = {'name' : structure['name'], 'structure_type' : structure['subtype'], 'resource' : resource}

        for field in resources_field_list:
            if (field in structure["resources"][resource]):
                editable_data += 1
                form_initial_data[field] = structure["resources"][resource][field]            

        form_initial_data_list.append(form_initial_data)

    if (structure['subtype'] == "host"):
        HostResourcesFormSet = formset_factory(HostResourcesForm, extra = 0)
        structure['resources_form'] = HostResourcesFormSet(initial = form_initial_data_list)
        structure['resources_form_helper'] = HostResourcesFormSetHelper()
        submit_button_disp = 5
    else:
        StructureResourcesFormSet = formset_factory(StructureResourcesForm, extra = 0)
        structure['resources_form'] = StructureResourcesFormSet(initial = form_initial_data_list)
        structure['resources_form_helper'] = StructureResourcesFormSetHelper()
        submit_button_disp = 7

    structure['resources_form_helper'].form_action = form_action
    structure['resources_editable_data'] = editable_data

    ## Need to do this to hide extra 'Save changes' buttons on JS
    structure['resources_form_helper'].layout[submit_button_disp][0].name += structure['name']

def getLimits(structure_name):
    url = base_url + "/structure/" + structure_name + "/limits"
    
    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}
    
    
    return data_json
  
def setLimitsForm(structure, form_action):

    editable_data = 0
    form_initial_data = {'name' : structure['name']}

    resource_list = ["cpu","mem","disk","net","energy"]

    for resource in resource_list:
        if (resource in structure['limits'] and 'boundary' in structure['limits'][resource]): 
            editable_data += 1
            form_initial_data[resource + '_boundary'] = structure['limits'][resource]['boundary']
    
    structure['limits_form'] = LimitsForm(initial = form_initial_data)
    structure['limits_form'].helper.form_action = form_action
    structure['limits_editable_data'] = editable_data
    
    for resource in resource_list:
        if ( not (resource in structure['limits'] and 'boundary' in structure['limits'][resource])):    
            structure['limits_form'].helper[resource + '_boundary'].update_attributes(type="hidden")

def setStartAppForm(structure, form_action, started_app):
    startAppForm = StartAppForm()
    startAppForm.fields['name'].initial = structure['name']
    startAppForm.helper.form_action = form_action

    structure['start_app_form'] = startAppForm
    structure['started_app'] = started_app



def setAddContainersForm(structures, hosts, form_action):

    host_list = {}
    for host in hosts:
        host_list[host['name']] = 0

    addContainersForm = AddContainersForm()
    addContainersForm.fields['host_list'].initial = json.dumps(host_list)

    addContainersForm.helper.form_action = form_action

    return addContainersForm

def setAddDisksToHostsForm(structures, form_action):

    addDisksToHostsForm = AddDisksToHostsForm()

    host_list = {}
    for host in structures:
        addDisksToHostsForm.fields['host_list'].choices.append((host['name'],host['name']))

    addDisksToHostsForm.helper.form_action = form_action

    return addDisksToHostsForm

def setRemoveStructureForm(structures, form_action):

    removeStructuresForm = RemoveStructureForm()
    removeStructuresForm.helper.form_action = form_action

    for structure in structures:
        if (form_action == "containers"):
            removeStructuresForm.fields['structures_removed'].choices.append(((structure['name'],structure['host']),structure['name']))
        else:
            removeStructuresForm.fields['structures_removed'].choices.append((structure['name'],structure['name']))

    return removeStructuresForm

def setRemoveContainersFromAppForm(app, containers, form_action):
    removeContainersFromAppForm = RemoveContainersFromAppForm()
    removeContainersFromAppForm.fields['app'].initial = app['name']
    removeContainersFromAppForm.fields['files_dir'].initial = app['files_dir']
    removeContainersFromAppForm.fields['install_script'].initial = app['install_script']
    removeContainersFromAppForm.fields['start_script'].initial = app['start_script']
    removeContainersFromAppForm.fields['stop_script'].initial = app['stop_script']

    removeContainersFromAppForm.helper.form_action = form_action

    editable_data = 0
    for container in containers:
        editable_data += 1
        disk_path = ""
        if 'disk' in container['resources']:
            disk_path = container['resources']['disk']['path']
        removeContainersFromAppForm.fields['containers_removed'].choices.append(((container['name'],container['host'],disk_path),container['name']))

    app['remove_containers_from_app_form'] = removeContainersFromAppForm
    app['remove_containers_from_app_editable_data'] = editable_data

# Process POST requests
def containers_guard_switch(request, container_name):

    guard_switch(request, container_name)
    return redirect("containers")

def hosts_guard_switch(request, container_name):

    guard_switch(request, container_name)
    return redirect("hosts")

def apps_guard_switch(request, structure_name):

    # we may be switching a container or an app

    guard_switch(request, structure_name)
    return redirect("apps")

def guard_switch(request, structure_name):

    state = request.POST['guard_switch']

    ## send put to stateDatabase
    url = base_url + "/structure/" + structure_name 

    if (state == "guard_off"):
        url += "/unguard"
    else:
        url += "/guard"

    req = urllib.request.Request(url, method='PUT')

    try:
        response = urllib.request.urlopen(req)
    except:
        pass

def processResources(request, url):

    structures_resources_field_list = ["guard","max","min"]
    hosts_resources_field_list = ["max"]

    errors = []

    if ("form-TOTAL_FORMS" in request.POST):
        total_forms = int(request.POST['form-TOTAL_FORMS'])

        if (total_forms > 0 and request.POST['form-0-operation'] == "resources"):
            
            name = request.POST['form-0-name']

            if (request.POST['form-0-structure_type'] == "host"):
                resources_field_list = hosts_resources_field_list
            else:
                resources_field_list = structures_resources_field_list     

            for i in range(0,total_forms,1):
                resource = request.POST['form-' + str(i) + "-resource"]
    
                for field in resources_field_list:
                    field_value = request.POST['form-' + str(i) + "-" + field]
                    error = processResourcesFields(request, url, name, resource, field, field_value)
                    if (len(error) > 0): errors.append(error)

    return errors

def processResourcesFields(request, url, structure_name, resource, field, field_value):

    full_url = url + structure_name + "/resources/" + resource + "/"

    if (field == "guard"):
        if (field_value == "True"): full_url += "guard"
        else:                       full_url += "unguard"
    
        r = requests.put(full_url)

    else:
        full_url += field
        headers = {'Content-Type': 'application/json'}

        new_value = field_value
        put_field_data = {'value': new_value.lower()}

        r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    error = ""
    if (r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error submiting " + field + " for structure " + structure_name + ": " + soup.get_text().strip()

    return error

def processLimits(request, url):

    errors = []

    if ("name" in request.POST and "operation" not in request.POST):
        
        structure_name = request.POST['name']

        resources = ["cpu","mem","disk","net","energy"]

        for resource in resources:
            if (resource + "_boundary" in request.POST):
                error = processLimitsBoundary(request, url, structure_name, resource, resource + "_boundary")
                if (len(error) > 0): errors.append(error)

    return errors

def processLimitsBoundary(request, url, structure_name, resource, boundary_name):

    full_url = url + structure_name + "/limits/" + resource + "/boundary"
    headers = {'Content-Type': 'application/json'}

    new_value = request.POST[boundary_name]

    r = ""
    if (new_value != ''):
        put_field_data = {'value': new_value.lower()}

        r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    error = ""
    if (r != "" and r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error submiting " + boundary_name + " for structure " + structure_name + ": " + soup.get_text().strip()

    return error

def processAdds(request, url):
    errors = []

    if ("operation" in request.POST and request.POST["operation"] == "add"):
        
        structure_type = request.POST['structure_type']
        resources = ["cpu","mem","disk","net","energy"]

        error = ""

        if (structure_type == "host"):
            host_name = request.POST['name']
            error = processAddHost(request, url, host_name, structure_type, resources)
        elif (structure_type == "container"):
            host_list = request.POST['host_list']
            error = processAddContainers(request, url, structure_type, resources, host_list)
        elif (structure_type == "apps"):
            app = request.POST['name']
            error = processAddApp(request, url, app, structure_type, resources)
        elif (structure_type == "containers_to_app"):
            app = request.POST['name']
            # containers_to_add = request.POST.getlist('containers_to_add', None)
            # for container in containers_to_add:
            #     error = processAddContainerToApp(request, url, app, container)
            #     if (len(error) > 0): errors.append(error)
            #     error = ""
            #     # Workaround to keep all updates to State DB
            #     time.sleep(0.25)

            #if ('fill_with_new_containers' in request.POST):
            #    error = processFillWithNewContainers(request, url, app)

            if ('number_of_containers' in request.POST):
                error = processStartApp(request, url, app)
        elif (structure_type == "disks_to_hosts"):
            error = processAddDisksToHosts(request, url, structure_type, resources)

        if (len(error) > 0): errors.append(error)

    return errors

def processAddHost(request, url, structure_name, structure_type, resources):
    error = ""

    new_containers = int(request.POST['number_of_containers'])
    cpu = int(request.POST['cpu_max'])
    mem = int(request.POST['mem_max'])
    energy = int(request.POST['energy_max']) if 'energy_max' in request.POST else None

    # disks
    disk_info = {}
    if config['disk_scaling']:
        disk_info['hdd_disks'] = int(request.POST['hdd_disks'])
        disk_info['ssd_disks'] = int(request.POST['ssd_disks'])
        disk_info['create_lvm'] = eval(request.POST['create_lvm'])
        if 'hdd_disks_path_list' in request.POST: disk_info['hdd_disks_path_list'] = request.POST['hdd_disks_path_list'].split(',')
        else: disk_info['hdd_disks_path_list']=[]
        if 'ssd_disks_path_list' in request.POST: disk_info['ssd_disks_path_list'] = request.POST['ssd_disks_path_list'].split(',')
        else: disk_info['ssd_disks_path_list']=[]
        if disk_info['create_lvm']: disk_info['lvm_path'] = request.POST['lvm_path']
        else: disk_info['lvm_path'] = ""

    # provision host and start its containers from playbook
    task = add_host_task.delay(structure_name,cpu,mem,disk_info,energy,new_containers)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"add_host_task")

    return error

def processAddDisksToHosts(request, url, structure_type, resources):

    error = ""

    if 'host_list' in request.POST:
        print(request.POST)
        host_list = request.POST.getlist('host_list', None)
        add_to_lv = eval(request.POST['add_to_lv'])
        new_disks = request.POST['new_disks'].split(',')
        extra_disk = request.POST['extra_disk']

        if add_to_lv and extra_disk == "":
            error = "Can't add disks to Logical Volume without an extra disk"
            return error

        # add disks from playbook
        task = add_disks_to_hosts_task.delay(host_list, add_to_lv, new_disks, extra_disk)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"add_disks_to_hosts_task")

    else:
        error = "No hosts selected"

    return error

def processAddContainers(request, url, structure_type, resources, host_list):

    error = ""
    container_resources = {}
    host_list = json.loads(host_list.replace("\'","\""))

    for resource in resources:
        if (resource + "_max" in request.POST):
            max_res = request.POST[resource + "_max"]
            min_res = request.POST[resource + "_min"]
            if max_res == "" or min_res == "":
                container_resources[resource + "_max"] = "0"
                container_resources[resource + "_min"] = "0"
            else:
                container_resources[resource + "_max"] = max_res
                container_resources[resource + "_min"] = min_res
        if (resource + "_boundary" in request.POST):
            if request.POST[resource + "_boundary"] != "":
                resource_boundary = request.POST[resource + "_boundary"]
            else:
                resource_boundary = int(int(container_resources[resource + "_min"]) * DEFAULT_BOUNDARY_PERCENTAGE)
                if resource_boundary == 0: resource_boundary = 1
            container_resources[resource + "_boundary"] = resource_boundary

    ## Bind specific disk
    bind_disk = "disk" in resources and "disk_max" in request.POST and request.POST["disk_max"] != "" and request.POST["disk_min"]

    # TODO: assign disks to containers in a more efficient way, instead of just choosing the same disk for all containers in the same host
    new_containers = {}
    disks = {}

    hosts_full_info = None
    if bind_disk:
        response = urllib.request.urlopen(base_url + "/structure/")
        data_json = json.loads(response.read())
        hosts_full_info = getHostsNames(data_json)

    for host in host_list:
        new_containers[host] = host_list[host]
        if bind_disk:
            for h in hosts_full_info:
                if h['name'] == host:
                    disks[host] = {}
                    disk = getFreestDisk(h)
                    disks[host]['name'] = disk
                    disks[host]['path'] = h['resources']['disks'][disk]['path']
                    break

    task = start_containers_task_v2.delay(new_containers, container_resources, disks)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"start_containers_task")

    return error

def processAddApp(request, url, structure_name, structure_type, resources):

    full_url = url + structure_type + "/" + structure_name
    headers = {'Content-Type': 'application/json'}

    # ## APP info
    # app_files = {}
    # for f in ['app_dir', 'files_dir', 'install_script', 'start_script', 'stop_script', 'app_jar']:
    #     if f in request.POST:
    #         app_files[f] = request.POST[f]
    #     else:
    #         app_files[f] = DEFAULT_APP_VALUES[f].format(app_name=app_files['app_name'])

    ## APP info
    app_files = {}
    # Mandatory fields
    if 'app_dir' in request.POST: app_files['app_dir'] = request.POST['app_dir']
    else: raise Exception("Missing mandatory parameter: {0}".format('app_dir'))

    # Optional parameters
    for f in ['start_script', 'stop_script', 'app_jar']:
        if f in request.POST and request.POST[f] != "":
            app_files[f] = request.POST[f]
        else:
            app_files[f] = DEFAULT_APP_VALUES[f]

    # Additional files
    for condition, additional_file in [('add_files_dir', 'files_dir'), ('add_install', 'install_script')]:
        if condition in request.POST and request.POST[condition]:
            if additional_file in request.POST and request.POST[additional_file] != "":
                app_files[additional_file] = request.POST[additional_file]
            else:
                app_files[additional_file] = DEFAULT_APP_VALUES[additional_file]
        else:
            app_files[additional_file] = ""

    put_field_data = {
        'app': {
            'name': structure_name,
            'resources': {},
            'guard': False,
            'subtype': "application",
            'files_dir': "{0}/{1}".format(app_files['app_dir'], app_files['files_dir']) if app_files['files_dir'] != "" else "",
            'install_script': "{0}/{1}".format(app_files['app_dir'], app_files['install_script']) if app_files['install_script'] != "" else "",
            'start_script': "{0}/{1}".format(app_files['app_dir'], app_files['start_script']) if app_files['start_script'] != "" else "",
            'stop_script': "{0}/{1}".format(app_files['app_dir'], app_files['stop_script']) if app_files['stop_script'] != "" else "",
            'app_jar': "{0}/{1}".format(app_files['app_dir'], app_files['app_jar']) if app_files['app_jar'] != "" else ""
        },
        'limits': {'resources': {}}
    }

    for resource in resources:
        if (resource + "_max" in request.POST):
            resource_max = int(request.POST[resource + "_max"])
            resource_min = int(request.POST[resource + "_min"])
            put_field_data['app']['resources'][resource] = {'max': resource_max, 'min': resource_min, 'guard': 'false'}

        if (resource + "_boundary" in request.POST):
            if request.POST[resource + "_boundary"] != "":
                resource_boundary = request.POST[resource + "_boundary"]
            else:
                resource_boundary = int(resource_min * DEFAULT_BOUNDARY_PERCENTAGE)
                if resource_boundary == 0: resource_boundary = 1
            put_field_data['limits']['resources'][resource] = {'boundary': resource_boundary}

    error = ""
    task = add_app_task.delay(full_url, headers, put_field_data, structure_name, app_files)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"add_app_task")

    return error

def processStartApp(request, url, app_name):

    headers = {'Content-Type': 'application/json'}

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

    app = getAppInfo(data_json, app_name)

    ## APP info
    app_files = {}
    if 'start_script' in app and app['start_script']: app_files['app_dir'] = os.path.dirname(app['start_script'])
    else: return "Error: there is no start script for app {0}".format(app_name)

    for f in ['files_dir', 'install_script', 'start_script', 'stop_script', 'app_jar']:
        if f in app:
            app_files[f] = os.path.basename(app[f])
        else:
            app_files[f] = ""

    app_resources = {}
    for resource in app['resources']:
        app_resources[resource] = {}
        app_resources[resource]['max'] = app['resources'][resource]['max']
        app_resources[resource]['current'] = 0 if 'current' not in app['resources'][resource] else app['resources'][resource]['current']
        app_resources[resource]['min'] = app['resources'][resource]['min']

    ## Containers to create
    number_of_containers = int(request.POST['number_of_containers'])
    benevolence = int(request.POST['benevolence'])

    # Check if there is space for app
    free_resources = {}
    for resource in app_resources:
        if resource in ['disk', 'energy']:
            continue
        free_resources[resource] = 0
        for host in hosts:
            free_resources[resource] += host['resources'][resource]['free']

    space_left_for_app = True
    for resource in free_resources:
        if free_resources[resource] < app_resources[resource]['max'] - app_resources[resource]['current']:
            space_left_for_app = False

    ## TODO: replace/add disk load check for disk I/O bandwidth check
    # Check if there is enough free disk load (specially important for Hadoop apps)
    if config['disk_scaling']:
        disk_load = number_of_containers
        free_disk_load = 0
        for host in hosts:
            free_disk_load += getHostFreeDiskLoad(host)

        if free_disk_load < disk_load: space_left_for_app = False

    error = ""
    if not space_left_for_app:
        error = "There is no space left for app {0}".format(app_name)
        return error

    is_hadoop_app = app_files['app_jar'] != ""

    if is_hadoop_app:
        ## ResourceManager/NameNode resources
        rm_maximum_cpu = 100
        rm_minimum_cpu = 100
        rm_cpu_boundary = 25
        rm_maximum_mem = 1024
        rm_minimum_mem = 1024
        rm_mem_boundary = 256
        app_resources['cpu']['max'] -= rm_maximum_cpu
        app_resources['cpu']['min'] -= rm_minimum_cpu
        app_resources['mem']['max'] -= rm_maximum_mem
        app_resources['mem']['min'] -= rm_minimum_mem

    # Get resources for containers
    container_resources = getContainerResourcesForApp(number_of_containers, app_resources, benevolence, is_hadoop_app)

    if is_hadoop_app:
        container_resources['rm-nn'] = {}
        container_resources['rm-nn']['cpu_max'] = rm_maximum_cpu
        container_resources['rm-nn']['cpu_min'] = rm_minimum_cpu
        container_resources['rm-nn']['cpu_boundary'] = rm_cpu_boundary
        container_resources['rm-nn']['mem_max'] = rm_maximum_mem
        container_resources['rm-nn']['mem_min'] = rm_minimum_mem
        container_resources['rm-nn']['mem_boundary'] = rm_mem_boundary

        number_of_containers += 1

    ## Container assignation to hosts
    assignation_policy = request.POST['assignation_policy']
    new_containers, disk_assignation, error = getContainerAssignationForApp(assignation_policy, hosts, number_of_containers, container_resources, app_name)
    if error != "": return error

    container_resources["regular"] = {x: str(y) for x, y in container_resources["regular"].items()}
    if "bigger" in container_resources:
        container_resources["irregular"] = {x: str(y) for x, y in container_resources["bigger"].items()}
    if "smaller" in container_resources:
        container_resources["irregular"] = {x: str(y) for x, y in container_resources["smaller"].items()}
    if "rm-nn" in container_resources:
        container_resources["rm-nn"] = {x: str(y) for x, y in container_resources["rm-nn"].items()}

    ## Get scaler polling frequency
    scaler_polling_freq = getScalerPollFreq()
    virtual_cluster = config['virtual_mode']

    if is_hadoop_app:
        task = start_hadoop_app_task.delay(url, headers, app_name, app_files, new_containers, container_resources, disk_assignation, scaler_polling_freq, virtual_cluster)
    else:
        task = start_app_task.delay(url, headers, app_name, app_files, new_containers, container_resources, disk_assignation, scaler_polling_freq)

    print("Starting task with id {0}".format(task.id))
    register_task(task.id, "{0}_app_task".format(app_name))

    return error


def getContainerResourcesForApp(number_of_containers, app_resources, benevolence, is_hadoop_app):

    container_resources = {}
    container_resources['regular'] = {}
    container_resources['regular']['cpu_max'] = (app_resources['cpu']['max'] - app_resources['cpu']['current']) / number_of_containers

    # CPU max shares allocation
    # We will try to allocate shares in multiples of 100
    correctly_allocated = False
    cpu_modulo = container_resources['regular']['cpu_max'] % 100
    if  cpu_modulo == 0 or is_hadoop_app:
        # we don't have to do anything
        # Workaround to avoid underusing resources in hadoop clusters: don't create smaller or bigger containers, since the whole cluster would be limited by the smaller container's resources
        correctly_allocated = True
    else:
        # Case 1: we create a bigger container
        if cpu_modulo < 50:
            # Check that it is actually possible for the containers to give shares
            if container_resources['regular']['cpu_max'] > 100:
                container_resources['bigger'] = container_resources['regular'].copy()
                container_resources['bigger']['cpu_max'] = container_resources['regular']['cpu_max'] + cpu_modulo*(number_of_containers - 1)
                container_resources['regular']['cpu_max'] -= cpu_modulo
                correctly_allocated = True
        # Case 2: we create a smaller container
        else:
            smaller_resources = container_resources['regular']['cpu_max'] - ((100 - cpu_modulo) * (number_of_containers - 1))
            # Check that the smaller container is not too small
            if smaller_resources >= 10:
                container_resources['smaller'] = container_resources['regular'].copy()
                container_resources['smaller']['cpu_max'] = smaller_resources
                container_resources['regular']['cpu_max'] += (100 - cpu_modulo)
                correctly_allocated = True

    # CPU min and other resources allocation
    if 'bigger' in container_resources or 'smaller' in container_resources:
        irregular = 'bigger' if 'bigger' in container_resources else 'smaller'

        # We will scale resources mantaining the original ratio with cpu_max
        # example: 400/100 max/min shares between 3 containers -> 133.333/33.333 shares each -> modified to 200/50 bigger container and 100/25 regular
        for resource in app_resources:
            for limit in ['max', 'min']:
                key = "{0}_{1}".format(resource, key)
                if key == "cpu_max":
                    continue
                resource_ratio = app_resources['cpu']['max'] / app_resources[resource][limit]

                for container_type in ['regular', irregular]:
                    container_resources[container_type][key] = container_resources[container_type]['cpu_max'] / resource_ratio

        # Adjust resource values to integer
        for resource in app_resources:
            for limit in ['max', 'min']:
                key = "{0}_{1}".format(resource, key)
                if key == "cpu_max":
                    continue

                resource_modulo = container_resources['regular'][key] % 1
                if resource_modulo < 0.5:
                    if container_resources['regular'][key] >= 1:
                        container_resources[irregular][key] = round(container_resources[irregular][key] + (resource_modulo * (number_of_containers - 1)))
                        container_resources['regular'][key] = int(container_resources['regular'][key])
                else:
                    smaller_resources = container_resources[irregular][key] - ((1 - resource_modulo) * (number_of_containers - 1))
                    if smaller_resources >= 1:
                        container_resources[irregular][key] = round(smaller_resources)
                        container_resources['regular'][key] = round(container_resources['regular'][key])
    else:
        for resource in app_resources:
            # MIN
            container_resources['regular']['{0}_min'.format(resource)] = int(app_resources[resource]['min'] / number_of_containers)

            # MAX
            if resource == 'cpu':
                continue
            container_resources['regular']['{0}_max'.format(resource)] = int((app_resources[resource]['max'] - app_resources[resource]['current']) / number_of_containers)

    # Boundaries are assigned based on max and min value of resource and the benevolence policy value
    # example: for 200/100 max/min cpu and a high benevolence value (or 'lax' limits) : boundary = (200-100)/4 = 25 -> actual minimum cpu (without takint into account rebalancing) 100+25*2 = 150
    # same example for low benevolence valye (or 'strict' limits) : boundary = (200-100)/16 = 6 -> actual minimum cpu 100+6*2 = 112
    if benevolence == 1: divider = 4
    elif benevolence == 2: divider = 8
    else: divider = 16

    for resource in app_resources:
        boundary_key = '{0}_boundary'.format(resource)
        max_key = '{0}_max'.format(resource)
        min_key = '{0}_min'.format(resource)
        container_resources['regular'][boundary_key] = round((container_resources['regular'][max_key] - container_resources['regular'][min_key]) / divider)

        if 'bigger' in container_resources or 'smaller' in container_resources:
            if 'bigger' in container_resources: irregular = 'bigger'
            else: irregular = 'smaller'
            container_resources[irregular][boundary_key] = round((container_resources[irregular][max_key] - container_resources[irregular][min_key]) / divider)

    if not correctly_allocated:
        # use original resource allocation
        pass

    # Round cpu max to integer
    container_resources["regular"]["cpu_max"] = round(container_resources["regular"]["cpu_max"])
    if "bigger" in container_resources: container_resources["bigger"]["cpu_max"] = round(container_resources["bigger"]["cpu_max"])
    if "smaller" in container_resources: container_resources["smaller"]["cpu_max"] = round(container_resources["smaller"]["cpu_max"])

    return container_resources

def getHostFreeDiskLoad(host):

    free_disk_load = 0

    if 'disks' in host['resources']:
        for disk_name in host['resources']['disks']:
            disk = host['resources']['disks'][disk_name]
            free_disk_load += max_load_dict[disk['type']] - disk['load']

    return free_disk_load

def getFreestDisk(host):

    freest_disk = None

    ## Based on load
    # current_min_load = -1

    # disk_type_load_ratio = {}
    # for disk_type in max_load_dict:
    #     disk_type_load_ratio[disk_type] = max_load_dict["LVM"]/max_load_dict[disk_type]

    # if 'disks' in host['resources']:
    #     for disk_name in host['resources']['disks']:

    #         disk = host['resources']['disks'][disk_name]

    #         if disk['load'] == 0:
    #             freest_disk = disk_name
    #             break

    #         if (disk['load'] == max_load_dict[disk['type']]): continue

    #         adjusted_load = disk['load'] * disk_type_load_ratio[disk['type']]

    #         if current_min_load == -1 or adjusted_load < current_min_load:
    #             current_min_load = adjusted_load
    #             freest_disk = disk_name

    ## Based on Bandwidth
    current_max_bw = -1

    if 'disks' in host['resources']:
        for disk_name in host['resources']['disks']:

            disk = host['resources']['disks'][disk_name]

            if (disk['free'] == 0): continue

            ## TODO: think if it is better to assign a disk with no containers but low bandwidth or a contended disk with high bw
            if disk['free'] == disk['max']:
                freest_disk = disk_name
                break

            if current_max_bw == -1 or disk['free'] > current_max_bw:
                current_max_bw = disk['free']
                freest_disk = disk_name

    return freest_disk

def GetFreestHost(hosts, container_resources, check_disks):

    freest_host = None
    current_min_disk_usage = -1

    for host in hosts:

        # Cyclic and Best-effort will now use allocate containers based on min resources instead of max to allow executing multiple containers that try to request all the availables resources from a host
        # Check cpu and mem space
        if host['resources']['cpu']['free'] < container_resources['cpu_min'] or host['resources']['mem']['free'] < container_resources['mem_min']:
            continue

        if not check_disks:
            freest_host = host
            break

        # Get disk usage percentage
        disk_usage = 0
        max_disk_usage = 0

        # Based on load
        # if 'disks' in host['resources']:
        #     for disk_name in host['resources']['disks']:
        #         disk = host['resources']['disks'][disk_name]
        #         max_disk_usage += max_load_dict[disk['type']]
        #         disk_usage += disk['load']

        ## Based on bandwidth
        ## TODO: think if it is better to assign a disk with no containers but low bandwidth or a contended disk with high bw
        if 'disks' in host['resources']:
            for disk_name in host['resources']['disks']:
                disk = host['resources']['disks'][disk_name]
                max_disk_usage += disk['max']
                disk_usage += (disk['max'] - disk['free'])

        if max_disk_usage == 0:
            continue

        disk_usage_percentage = disk_usage / max_disk_usage

        if disk_usage_percentage == 0:
            freest_host = host
            break

        if current_min_disk_usage == -1 or disk_usage_percentage < current_min_disk_usage:
            current_min_disk_usage = disk_usage_percentage
            freest_host = host

    return freest_host


def getHostFreeDiskBw(host):

    free_host_bw = 0

    if 'disks' in host['resources']:
        for disk_name in host['resources']['disks']:
            disk = host['resources']['disks'][disk_name]
            free_host_bw += disk['free']

    return free_host_bw

def getContainerAssignationForApp(assignation_policy, hosts, number_of_containers, container_resources, app_name):

    error = ""
    new_containers = {}
    disk_assignation = {}

    irregular_container_to_allocate = 0
    hadoop_container_to_allocate = 0
    if "smaller" in container_resources or "bigger" in container_resources:
        irregular_container_to_allocate = 1
    if "rm-nn" in container_resources:
        hadoop_container_to_allocate = 1
    containers_to_allocate = number_of_containers - irregular_container_to_allocate - hadoop_container_to_allocate

    assignation = {}
    for host in hosts:
        assignation[host['name']] = {}
        assignation[host['name']]["regular"] = 0
        if config['disk_scaling'] and 'disks' in host['resources']:
            disk_assignation[host['name']] = {}
            for disk_name in host['resources']['disks']:
                disk = host['resources']['disks'][disk_name]
                disk_assignation[host['name']][disk_name] = {}
                disk_assignation[host['name']][disk_name]['new_containers'] = 0
                disk_assignation[host['name']][disk_name]['disk_path'] = disk['path']
                #disk_assignation[host['name']][disk_name]['max_load'] = max_load_dict[disk['type']] - disk['load']
                disk_assignation[host['name']][disk_name]['free_bw'] = disk['free']

    if assignation_policy == "Fill-up":
        for host in hosts:
            free_cpu = host['resources']['cpu']['free']
            free_mem = host['resources']['mem']['free']
            #free_disk_load = getHostFreeDiskLoad(host)
            if config['disk_scaling']: free_bw_host = getHostFreeDiskBw(host)

            if containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate <= 0:
                break
            # First we try to assign the bigger container if it exists
            if irregular_container_to_allocate > 0 and "bigger" in container_resources and free_cpu >= container_resources["bigger"]['cpu_max'] and free_mem >= container_resources["bigger"]['mem_max']:
                if not config['disk_scaling'] or free_bw_host > container_resources["bigger"]['disk_max']:
                    assignation[host['name']]["irregular"] = 1
                    irregular_container_to_allocate = 0
                    free_cpu -= container_resources["bigger"]['cpu_max']
                    free_mem -= container_resources["bigger"]['mem_max']
                    if config['disk_scaling']:
                        free_bw_host -= container_resources["bigger"]['disk_max']
                        for disk in disk_assignation[host['name']]:
                            if disk_assignation[host['name']][disk]['free_bw'] > container_resources["bigger"]['disk_max']:
                                disk_assignation[host['name']][disk]['free_bw'] -= container_resources["bigger"]['disk_max']
                                disk_assignation[host['name']][disk]['new_containers'] += 1
                                break

            while containers_to_allocate > 0 and free_cpu >= container_resources["regular"]['cpu_max'] and free_mem >= container_resources["regular"]['mem_max']:
                if config['disk_scaling'] and free_bw_host > container_resources["regular"]['disk_max']: break
                assignation[host['name']]["regular"] += 1
                containers_to_allocate -= 1
                free_cpu -= container_resources['regular']['cpu_max']
                free_mem -= container_resources['regular']['mem_max']
                if config['disk_scaling']:
                    free_bw_host -= container_resources['regular']['disk_max']
                    for disk in disk_assignation[host['name']]:
                        if disk_assignation[host['name']][disk]['free_bw'] > container_resources['regular']['disk_max']:
                            disk_assignation[host['name']][disk]['free_bw'] -= container_resources['regular']['disk_max']
                            disk_assignation[host['name']][disk]['new_containers'] += 1
                            break

            # We try to assign the smaller container if it exists
            if irregular_container_to_allocate > 0 and "smaller" in container_resources and free_cpu >= container_resources["smaller"]['cpu_max'] and free_mem >= container_resources["smaller"]['mem_max']:
                if not config['disk_scaling'] or free_bw_host > container_resources["smaller"]['disk_max']:
                    assignation[host['name']]["irregular"] = 1
                    irregular_container_to_allocate = 0
                    free_cpu -= container_resources["smaller"]['cpu_max']
                    free_mem -= container_resources["smaller"]['mem_max']
                    if config['disk_scaling']:
                        free_bw_host -= container_resources["smaller"]['disk_max']
                        for disk in disk_assignation[host['name']]:
                            if disk_assignation[host['name']][disk]['free_bw'] > container_resources["smaller"]['disk_max']:
                                disk_assignation[host['name']][disk]['free_bw'] -= container_resources["smaller"]['disk_max']
                                disk_assignation[host['name']][disk]['new_containers'] += 1
                                break

            # Lastly we try to assign the resourcemanager/namenode container if it exists
            if hadoop_container_to_allocate > 0 and "rm-nn" in container_resources and free_cpu >= container_resources["rm-nn"]['cpu_max'] and free_mem >= container_resources["rm-nn"]['mem_max']:
                assignation[host['name']]["rm-nn"] = 1
                hadoop_container_to_allocate = 0
                free_cpu -= container_resources["rm-nn"]['cpu_max']
                free_mem -= container_resources["rm-nn"]['mem_max']

    # Cyclic and Best-effort will now use allocate containers based on min resources instead of max to allow executing multiple containers that try to request all the availables resources from a host
    elif assignation_policy == "Cyclic":
        hosts_without_space = 0
        while containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate > 0 and hosts_without_space < len(hosts):
            for host in hosts:
                if containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate <= 0 or hosts_without_space >= len(hosts):
                    break

                #free_disk_load = getHostFreeDiskLoad(host)
                if config['disk_scaling']: free_bw_host = getHostFreeDiskBw(host)

                container_allocated = False
                for container_type in ['bigger', 'regular', 'smaller', 'rm-nn']:
                    if container_type == 'bigger' or container_type == 'smaller':
                        containers_to_check = irregular_container_to_allocate
                    elif container_type == 'rm-nn':
                        containers_to_check = hadoop_container_to_allocate
                    elif container_type == 'regular':
                        containers_to_check = containers_to_allocate

                    if containers_to_check > 0 and container_type in container_resources and host['resources']['cpu']['free'] >= container_resources[container_type]['cpu_min'] and host['resources']['mem']['free'] >= container_resources[container_type]['mem_min']:
                        if not config['disk_scaling'] or container_type == "rm-nn" or free_bw_host > container_resources[container_type]['disk_min']:
                            if container_type == 'bigger' or container_type == 'smaller':
                                assignation[host['name']]["irregular"] = 1
                                irregular_container_to_allocate = 0
                            elif container_type == 'rm-nn':
                                assignation[host['name']]["rm-nn"] = 1
                                hadoop_container_to_allocate = 0
                            elif container_type == 'regular':
                                assignation[host['name']]['regular'] += 1
                                containers_to_allocate -= 1

                            host['resources']['cpu']['free'] -= container_resources[container_type]['cpu_min']
                            host['resources']['mem']['free'] -= container_resources[container_type]['mem_min']

                            if config['disk_scaling'] and container_type != "rm-nn":
                                host_disk = getFreestDisk(host)
                                if host_disk == None: break

                                if disk_assignation[host['name']][host_disk]['free_bw'] > container_resources[container_type]['disk_min']:
                                    disk_assignation[host['name']][host_disk]['free_bw'] -= container_resources[container_type]['disk_min']
                                    disk_assignation[host['name']][host_disk]['new_containers'] += 1
                                    for disk_name in host['resources']['disks']:
                                        disk = host['resources']['disks'][disk_name]
                                        if disk_name == host_disk:
                                            disk['free'] -= container_resources[container_type]['disk_min']
                                            break

                            container_allocated = True
                            break

                if not container_allocated:
                    hosts_without_space += 1

    elif assignation_policy == "Best-effort":
        while containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate > 0:

            container_allocated = False
            for container_type in ['bigger', 'regular', 'smaller', 'rm-nn']:
                if container_type == 'bigger' or container_type == 'smaller':
                    containers_to_check = irregular_container_to_allocate
                elif container_type == 'rm-nn':
                    containers_to_check = hadoop_container_to_allocate
                elif container_type == 'regular':
                    containers_to_check = containers_to_allocate

                if containers_to_check > 0 and container_type in container_resources:

                    if not config['disk_scaling'] or container_type == 'rm-nn':
                        check_disks = False
                    else:
                        check_disks = True

                    freest_host = GetFreestHost(hosts, container_resources[container_type], check_disks)
                    if freest_host == None:
                        break

                    if container_type == 'bigger' or container_type == 'smaller':
                        assignation[freest_host['name']]["irregular"] = 1
                        irregular_container_to_allocate = 0
                    elif container_type == 'rm-nn':
                        assignation[freest_host['name']]["rm-nn"] = 1
                        hadoop_container_to_allocate = 0
                    elif container_type == 'regular':
                        assignation[freest_host['name']]['regular'] += 1
                        containers_to_allocate -= 1

                    freest_host['resources']['cpu']['free'] -= container_resources[container_type]['cpu_min']
                    freest_host['resources']['mem']['free'] -= container_resources[container_type]['mem_min']

                    if config['disk_scaling'] and container_type != "rm-nn":
                        host_disk = getFreestDisk(freest_host)
                        if host_disk == None: break

                        if disk_assignation[freest_host['name']][host_disk]['free_bw'] > container_resources[container_type]['disk_min']:
                            disk_assignation[freest_host['name']][host_disk]['free_bw'] -= container_resources[container_type]['disk_min']
                            disk_assignation[freest_host['name']][host_disk]['new_containers'] += 1
                            for disk_name in freest_host['resources']['disks']:
                                disk = host['resources']['disks'][disk_name]
                                if disk_name == host_disk:
                                    disk['free'] -= container_resources[container_type]['disk_min']
                                    break

                    container_allocated = True
                    break

            if not container_allocated:
                break

    if containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate > 0:
        error = "Could not allocate containers for app {0}: {1}".format(app_name, container_resources)
        return new_containers, disk_assignation, error

    new_containers = {x:y for x,y in assignation.items() if y['regular'] > 0 or "irregular" in y or "rm-nn" in y}

    return new_containers, disk_assignation, error

def apps_stop_switch(request, structure_name):

    url = base_url + "/structure/"
    headers = {'Content-Type': 'application/json'}

    app_containers, app_files = getContainersFromApp(url, structure_name)

    container_list = []
    for container in app_containers:
        disk_path = ""
        if 'disk' in container['resources']:
            disk_path = container['resources']['disk']['path']

        container_list.append("({0},{1},{2})".format(container['name'],container['host'], disk_path))

    error = processRemoveContainersFromApp(url, container_list, structure_name, app_files)
    if (len(error) > 0): errors.append(error)

    return redirect("apps")

def processRemoves(request, url, structure_type):

    errors = []

    if ("operation" in request.POST and request.POST["operation"] == "remove"):
        
        if ("structures_removed" in request.POST):

            structures_to_remove = request.POST.getlist('structures_removed', None)
            error = processRemoveStructures(request, url, structures_to_remove, structure_type)
            if (len(error) > 0): errors.append(error)

        elif ("containers_removed" in request.POST):
            ## Remove containers from app scenario
            containers_to_remove = request.POST.getlist('containers_removed', None)
            app = request.POST['app']
            app_files = {}
            app_files['files_dir'] = os.path.basename(request.POST['files_dir'])
            app_files['install_script'] = os.path.basename(request.POST['install_script'])
            app_files['start_script'] = os.path.basename(request.POST['start_script'])
            app_files['stop_script'] = os.path.basename(request.POST['stop_script'])
            app_files['app_dir'] = os.path.dirname(request.POST['start_script'])
            if 'app_jar' in request.POST: app_files['app_jar'] = os.path.basename(request.POST['app_jar'])
            else: app_files['app_jar'] = ""

            error = processRemoveContainersFromApp(url, containers_to_remove, app, app_files)
            if (len(error) > 0): errors.append(error)

    return errors    

def processRemoveStructures(request, url, structure_list, structure_type):

    structure_type_url = ""
    headers = {'Content-Type': 'application/json'}

    if (structure_type == "containers"):
        structure_type_url = "container"

        container_list = []
        for structure in structure_list:
            cont_host = structure.strip("(").strip(")").split(',')
            container = cont_host[0].strip().strip("'")
            host = cont_host[1].strip().strip("'")

            container_list.append({'container_name': container, 'host': host})

        task = remove_containers.delay(url, headers, container_list)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"remove_containers_task")

    elif (structure_type == "hosts"):
        structure_type_url = "host"

        for host in structure_list:
            container_list = getContainersFromHost(url, host)
            container_list = ["({0},{1})".format(container, host) for container in container_list]

            processRemoveStructures(request, url, container_list, "containers")

            full_url = url + structure_type_url + "/" + host

            task = remove_host_task.delay(full_url, headers, host)
            print("Starting task with id {0}".format(task.id))
            register_task(task.id,"remove_host_task")

    elif (structure_type == "apps"):
        structure_type_url = "apps"

        for app in structure_list:
            container_list, app_files = getContainersFromApp(url, app)

            task = remove_app_task.delay(url, structure_type_url, headers, app, container_list, app_files)
            print("Starting task with id {0}".format(task.id))
            register_task(task.id,"remove_app_task")

    error = ""
    return error

def processRemoveContainersFromApp(url, container_host_duples, app, app_files):

    container_list = []
    for cont_hosts in container_host_duples:
        cont_host = cont_hosts.strip("(").strip(")").split(',')
        container = cont_host[0].strip().strip("'")
        host = cont_host[1].strip().strip("'")
        disk_path = cont_host[2].strip().strip("'")

        container_list.append({'container_name': container, 'host': host, 'disk_path': disk_path})

    headers = {'Content-Type': 'application/json'}

    scaler_polling_freq = getScalerPollFreq()

    task = remove_containers_from_app.delay(url, headers, container_list, app, app_files, scaler_polling_freq)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"remove_containers_from_app")

    error = ""
    return error

def getContainersFromHost(url, host_name):

    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
    except urllib.error.HTTPError:
        data = {}

    containerList = []

    for item in data:
        if (item['subtype'] == 'container' and item['host'] == host_name):
            containerList.append(item['name'])

    return containerList

def getContainersFromApp(url, app_name):

    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
    except urllib.error.HTTPError:
        data = {}

    containerList = []
    containerNamesList = []
    app_files = {}
    app_files['files_dir'] = ""
    app_files['install_script'] = ""
    app_files['start_script'] = ""
    app_files['stop_script'] = ""
    app_files['app_jar'] = ""

    for item in data:
        if (item['subtype'] == 'application' and item['name'] == app_name):
            containerNamesList = item['containers']
            app_files['files_dir'] = os.path.basename(item['files_dir'])
            app_files['install_script'] = os.path.basename(item['install_script'])
            app_files['start_script'] = os.path.basename(item['start_script'])
            app_files['stop_script'] = os.path.basename(item['stop_script'])
            app_files['app_jar'] = os.path.basename(item['app_jar'])
            app_files['app_dir'] = os.path.dirname(item['start_script'])

    for item in data:
        if (item['subtype'] == 'container' and item['name'] in containerNamesList):
            containerList.append(item)

    return containerList, app_files

## Services
def services(request):
    url = base_url + "/service/"

    database_snapshoter_options = ["debug","documents_persisted","polling_frequency"]
    guardian_options = ["cpu_shares_per_watt", "debug", "event_timeout","guardable_resources","structure_guarded","window_delay","window_timelapse","energy_model_name","use_energy_model"]
    scaler_options = ["check_core_map","debug","polling_frequency","request_timeout"]
    structures_snapshoter_options = ["polling_frequency","debug","persist_apps","resources_persisted"]
    sanity_checker_options = ["debug","delay"]
    refeeder_options = ["debug","generated_metrics","polling_frequency","window_delay","window_timelapse"]
    rebalancer_options = ["debug","rebalance_users","energy_diff_percentage","energy_stolen_percentage","window_delay","window_timelapse"]
    energy_manager_options = ["polling_frequency", "debug"]
    watt_trainer_options = ["window_timelapse", "window_delay", "generated_metrics", "models_to_train", "debug"]

    if (len(request.POST) > 0):
        if ("name" in request.POST):
            errors = []

            service_name = request.POST['name']

            options = []

            if (service_name == 'database_snapshoter'):     options = database_snapshoter_options

            elif (service_name == 'guardian'):              options = guardian_options

            elif (service_name == 'scaler'):                options = scaler_options

            elif (service_name == 'structures_snapshoter'): options = structures_snapshoter_options

            elif (service_name == 'sanity_checker'):        options = sanity_checker_options

            elif (service_name == 'refeeder'):              options = refeeder_options

            elif (service_name == 'rebalancer'):            options = rebalancer_options

            elif (service_name == 'energy_manager'):        options = energy_manager_options

            elif (service_name == 'watt_trainer'):          options = watt_trainer_options

            for option in options:
                error = processServiceConfigPost(request, url, service_name, option)
                if (len(error) > 0): errors.append(error)

        return redirect_with_errors('services',errors)

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    requests_errors = request.GET.getlist("errors", None)
    requests_successes = request.GET.getlist("success", None)
    requests_info = []

    ## Pending tasks
    still_pending_tasks, successful_tasks, failed_tasks = get_pendings_tasks_to_string()
    requests_errors.extend(failed_tasks)
    requests_successes.extend(successful_tasks)
    requests_info.extend(still_pending_tasks)

    ## get datetime in epoch to compare later with each service's heartbeat
    now = time.time()

    not_recognized_services = []
    for item in data_json:

        form_initial_data = {'name' : item['name']}
        editable_data = 0
        
        serviceForm = {}

        if (item['name'] == 'database_snapshoter'):
            for option in database_snapshoter_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = DBSnapshoterForm(initial = form_initial_data)

        elif (item['name'] == 'guardian'):
            for option in guardian_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = GuardianForm(initial = form_initial_data)

        elif (item['name'] == 'scaler'):
            for option in scaler_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = ScalerForm(initial = form_initial_data)

        elif (item['name'] == 'structures_snapshoter'):
            for option in structures_snapshoter_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = StructuresSnapshoterForm(initial = form_initial_data)

        elif (item['name'] == 'sanity_checker'):
            for option in sanity_checker_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = SanityCheckerForm(initial = form_initial_data)

        elif (item['name'] == 'refeeder'):
            for option in refeeder_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = RefeederForm(initial = form_initial_data)

        elif (item['name'] == 'rebalancer'):
            for option in rebalancer_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = ReBalancerForm(initial = form_initial_data)

        elif (item['name'] == 'energy_manager'):
            for option in watt_trainer_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = EnergyManagerForm(initial = form_initial_data)

        elif (item['name'] == 'watt_trainer'):
            for option in watt_trainer_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = WattTrainerForm(initial = form_initial_data)
        
        else:
            not_recognized_services.append(item)
            continue # Not recognized service

        item['form'] = serviceForm
        item['editable_data'] = editable_data

        try:
            item['alive'] = (now - item['heartbeat']) < 60
        except Exception:
            item['alive'] = False

    config_errors = checkInvalidConfig()

    # Remove not recognized services
    for item in not_recognized_services:
        data_json.remove(item)

    return render(request, 'services.html', {'data': data_json, 'config_errors': config_errors, 'requests_errors': requests_errors, 'requests_successes': requests_successes, 'requests_info': requests_info})
  
def service_switch(request,service_name):

    state = request.POST['service_switch']

    ## send put to stateDatabase
    url = base_url + "/service/" + service_name + "/ACTIVE"

    if (state == "service_off"):
        activate = "false"
    else:
        activate = "true"

    headers = {'Content-Type': 'application/json'}

    put_field_data = {'value': activate}
    r = requests.put(url, data=json.dumps(put_field_data), headers=headers)

    if (r.status_code != requests.codes.ok):
        ## shouldn't happen
        print(r.content)

    return redirect('services')

def processServiceConfigPost(request, url, service_name, config_name):

    full_url = url + service_name + "/" + config_name.upper()
    headers = {'Content-Type': 'application/json'}

    json_fields = []
    multiple_choice_fields = ["guardable_resources","resources_persisted","generated_metrics","documents_persisted"]

    r = ""

    if (config_name in json_fields):
        ## JSON field request (not used at the moment)
        new_value = request.POST[config_name]
        new_values_list = new_value.strip("[").strip("]").split(",")
        put_field_data = json.dumps({"value":[v.strip().strip('"') for v in new_values_list]})

        r = requests.put(full_url, data=put_field_data, headers=headers)

    elif (config_name in multiple_choice_fields):
        ## MultipleChoice field request
        new_values_list = request.POST.getlist(config_name)
        put_field_data = json.dumps({"value":[v.strip().strip('"') for v in new_values_list]})

        r = requests.put(full_url, data=put_field_data, headers=headers)

    else:
        ## Other field request
        new_value = request.POST[config_name]
        
        if (new_value != ''):
            put_field_data = {'value': new_value.lower()}
            r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    error = ""
    if (r != "" and r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error submiting " + config_name + " for service " + service_name + ": " + soup.get_text().strip()

    return error


## Rules
def rules(request):
    url = base_url + "/rule/"

    if (len(request.POST) > 0):
        errors = []

        rule_name = request.POST['name']
        rules_fields = ["amount","rescale_policy","up_events_required","down_events_required"]
        rules_fields_put_url = ["amount","policy","events_required","events_required"]
        rules_fields_dict = dict(zip(rules_fields, rules_fields_put_url))

        for field in rules_fields:
            if (field in request.POST):
                error = processRulesPost(request, url, rule_name, field, rules_fields_dict[field])
                if (len(error) > 0): errors.append(error)

        return redirect_with_errors('rules',errors)

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    requests_errors = request.GET.getlist("errors", None)
    requests_successes = request.GET.getlist("success", None)
    requests_info = []

    ## Pending tasks
    still_pending_tasks, successful_tasks, failed_tasks = get_pendings_tasks_to_string()
    requests_errors.extend(failed_tasks)
    requests_successes.extend(successful_tasks)
    requests_info.extend(still_pending_tasks)

    for item in data_json:
        item['rule_readable'] = jsonBooleanToHumanReadable(item['rule'])

        form_initial_data = {'name' : item['name']}
        editable_data = 0
        
        if ('amount' in item):
            editable_data += 1
            form_initial_data['amount'] = item['amount']

        if ('rescale_policy' in item and 'rescale_type' in item and item['rescale_type'] == "up"):
            editable_data += 1
            form_initial_data['rescale_policy'] = item['rescale_policy']

        rule_words = item['rule_readable'].split(" ")
        if ('events.scale.down' in rule_words):
            index = rule_words.index("events.scale.down")
            value = rule_words[index + 2]
            editable_data += 1
            form_initial_data['down_events_required'] = value

        if ('events.scale.up' in rule_words):
            index = rule_words.index("events.scale.up")
            value = rule_words[index + 2]
            editable_data += 1
            form_initial_data['up_events_required'] = value

        ruleForm=RuleForm(initial = form_initial_data)

        if ('amount' not in item):
            ruleForm.helper['amount'].update_attributes(type="hidden")

        if (not ('rescale_policy' in item and 'rescale_type' in item and item['rescale_type'] == "up")):
            ruleForm.helper['rescale_policy'].update_attributes(type="hidden")

        if ('events.scale.down' not in rule_words):
            ruleForm.helper['down_events_required'].update_attributes(type="hidden")

        if ('events.scale.up' not in rule_words):    
            ruleForm.helper['up_events_required'].update_attributes(type="hidden")

        item['form'] = ruleForm
        item['editable_data'] = editable_data

    rulesResources = getRulesResources(data_json)
    ruleTypes = ['requests','events','']

    config_errors = checkInvalidConfig()

    return render(request, 'rules.html', {'data': data_json, 'resources':rulesResources, 'types':ruleTypes, 'config_errors': config_errors, 'requests_errors': requests_errors, 'requests_successes': requests_successes, 'requests_info': requests_info})

def getRulesResources(data):
    resources = []
    
    for item in data:
        if (item['resource'] not in resources):
            resources.append(item['resource'])
    
    return resources

def jsonBooleanToHumanReadable(jsonBoolExpr):

    boolString = ""

    boolOperators = ['and','or','==','>=','<=','<','>','+','-','*','/']

    ## Check if dict or literal
    if type(jsonBoolExpr) is dict:
        firstElement = list(jsonBoolExpr.keys())[0]
    else:
        firstElement = jsonBoolExpr


    if (firstElement in boolOperators):
        ## Got bool expression
        jsonBoolValues = jsonBoolExpr[firstElement]
        for i in range(0, len(jsonBoolValues)):
            boolString += jsonBooleanToHumanReadable(jsonBoolValues[i])
            if (i < len(jsonBoolValues) - 1):
                boolString += " " + firstElement.upper() + " "

    elif (firstElement == 'var'):
        ## Got variable
        boolString = jsonBoolExpr[firstElement]

    else:
        ## Got literal
        boolString = str(firstElement)      

    return boolString

def rule_switch(request,rule_name):

    state = request.POST['rule_switch']

    ## send put to stateDatabase
    url = base_url + "/rule/" + rule_name 

    if (state == "rule_off"):
        url += "/deactivate"
    else:
        url += "/activate"

    req = urllib.request.Request(url, method='PUT')

    try:
        response = urllib.request.urlopen(req)
    except:
        pass

    return redirect('rules')

def processRulesPost(request, url, rule_name, field, field_put_url):

    full_url = url + rule_name + "/" + field_put_url
    headers = {'Content-Type': 'application/json'}

    new_value = request.POST[field]

    r = ""
    if (new_value != ''):
        put_field_data = {'value': new_value}

        if (field_put_url == "events_required"):
            if (field == "up_events_required"):
                event_type = "up"
            else:
                event_type = "down"

            put_field_data['event_type'] = event_type
                
        r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    error = ""
    if (r != "" and r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error submiting " + field + " for rule " + rule_name + ": " + soup.get_text().strip()

    return error

## Check Invalid Config
def checkInvalidConfig():
    error_lines = []

    vars_path = "../../vars/main.yml"
    with open(vars_path, "r") as vars_file:
        vars_config = yaml.load(vars_file, Loader=yaml.FullLoader)

    installation_path = vars_config['installation_path']

    if installation_path.startswith("{{ lookup('env', 'HOME') }}"):
        home_directory = os.path.expanduser("~")
        installation_path = installation_path.replace("{{ lookup('env', 'HOME') }}", home_directory)

    serverless_containers_path = installation_path + "/ServerlessContainers"

    full_path = serverless_containers_path + "/sanity_checker.log"

    with open(full_path, 'r') as file:
        lines = file.readlines()
        lines.reverse()

    ## find last "Sanity checked" message
    i = 0
    while (i < len(lines) and "Sanity checked" not in lines[i]):
        i+= 1

    ## find last "Checking for invalid configuration" message
    i += 1
    while (i < len(lines) and "Checking for invalid configuration" not in lines[i]):
        error_lines.append(lines[i])
        i += 1

    error_lines.reverse()

    return error_lines


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
    headers = {'Content-Type': 'application/json'}
    app_files = {}
    app_files['files_dir'] = request.POST['files_dir']
    app_files['install_script'] = request.POST['install_script']
    app_files['start_script'] = request.POST['start_script']
    app_files['stop_script'] = request.POST['stop_script']

    for host in newContainers:
        task = start_containers_with_app_task.delay(url, headers, host, newContainers[host], app, app_files)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"add_container_to_app_task")

    error = ""
    return error

## Not used ATM
def processAddHost_via_API(request, url, structure_name, structure_type, resources):

    full_url = url + structure_type + "/" + structure_name
    headers = {'Content-Type': 'application/json'}

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

    r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    error = ""
    if (r != "" and r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error adding host " + structure_name + ": " + soup.get_text().strip()

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

    headers = {'Content-Type': 'application/json'}
    full_url = url + "container/{0}/{1}".format(container,app)

    task = add_container_to_app_task.delay(full_url, headers, host, container, app, app_files)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"add_container_to_app_task")

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
    headers = {'Content-Type': 'application/json'}

    r = requests.delete(full_url, headers=headers)

    error = ""
    if (r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error removing structure " + structure_name + ": " + soup.get_text().strip()

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
    headers = {'Content-Type': 'application/json'}

    if (structure_type == "containers"):
        structure_type_url = "container"
        cont_host = structure_name.strip("(").strip(")").split(',')
        structure_name = cont_host[0].strip().strip("'")
        host_name = cont_host[1].strip().strip("'")

        full_url = url + structure_type_url + "/" + structure_name

        task = remove_container_task.delay(full_url, headers, host_name, structure_name)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"remove_container_task")

    elif (structure_type == "hosts"):
        structure_type_url = "host"
        containerList = getContainersFromHost(url, structure_name)

        for container in containerList:
            processRemoveStructure(request, url, "(" + container + "," + structure_name + ")", "containers")

        full_url = url + structure_type_url + "/" + structure_name

        task = remove_host_task.delay(full_url, headers, structure_name)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"remove_host_task")

    elif (structure_type == "apps"):
        structure_type_url = "apps"
        containerList, app_files = getContainersFromApp(url, structure_name)

        task = remove_app_task.delay(url, structure_type_url, headers, structure_name, containerList, app_files)
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
    headers = {'Content-Type': 'application/json'}

    task = remove_container_from_app_task.delay(full_url, headers, host, container_name, disk_path , app, app_files, "")
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"remove_container_from_app_task")

    error = ""
    return error