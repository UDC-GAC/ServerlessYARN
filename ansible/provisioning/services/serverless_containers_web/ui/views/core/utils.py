import re
import os
import json
import yaml
import functools
import urllib

from django.forms import formset_factory
from django.shortcuts import redirect
from django.conf import settings

from ui.utils import MAX_DISK_LOAD_DICT, EXCLUDED_VALUES_LABELS
from ui.forms import LimitsForm, StructureResourcesForm, StructureResourcesFormSetHelper, HostResourcesForm, HostResourcesFormSetHelper, UserResourcesForm, UserResourcesFormSetHelper, RemoveStructureForm


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


def redirect_with_errors(redirect_url, errors):
    red = redirect(redirect_url)
    if len(errors) > 0:
        red['Location'] += '?errors=' + urllib.parse.quote(errors[0])
        i = 1
        while(i < len(errors)):
            red['Location'] += '&errors=' + urllib.parse.quote(errors[i])
            i += 1
    else:
        red['Location'] += '?success=' + "Requests were successful!"

    return red


def guard_switch(request, structure_name):
    state = request.POST['guard_switch']
    ## send put to stateDatabase
    url = settings.BASE_URL + "/structure/" + structure_name
    url += "/unguard" if state == "guard_off" else "/guard"
    req = urllib.request.Request(url, method='PUT')
    try:
        response = urllib.request.urlopen(req)
    except:
        pass


def getScalerPollFreq():
    url = settings.BASE_URL + "/service/scaler"
    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())

    return data_json.get('config', {}).get('POLLING_FREQUENCY', 5)


def checkInvalidConfig():
    error_lines = []
    #vars_path = "../../vars/main.yml"
    #with open(vars_path, "r") as vars_file:
    #    vars_config = yaml.load(vars_file, Loader=yaml.FullLoader)

    installation_path = settings.VARS_CONFIG['installation_path']
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
    while i < len(lines) and "Sanity checked" not in lines[i]:
        i+= 1

    ## find last "Checking for invalid configuration" message
    i += 1
    while i < len(lines) and "Checking for invalid configuration" not in lines[i]:
        error_lines.append(lines[i])
        i += 1

    error_lines.reverse()

    return error_lines


# ------------------------------------ Common functions for resource/limits management ------------------------------------

def getLimits(structure_name):
    url = settings.BASE_URL + "/structure/" + structure_name + "/limits"
    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}

    return data_json

def getStructuresValuesLabels(item, field):
    values_labels = set()
    for key, values in item.get(field, {}).items():
        if key != "cpu_cores":
            for value_label in values:
                if value_label not in EXCLUDED_VALUES_LABELS:
                    values_labels.add(value_label)
    return list(values_labels)


def setStructureResourcesForm(structure, form_action):
    editable_data = 0
    full_resource_list = ["cpu", "mem", "disk_read", "disk_write", "net", "energy"]
    structures_resources_field_list = ["guard", "max", "min", "weight"]
    user_resources_field_list = ["max", "min"]
    host_resources_field_list = ["max"]
    form_initial_data_list = []

    resource_list = []
    for resource in full_resource_list:
        if resource in structure['resources']:
            resource_list.append(resource)

    if structure['subtype'] == "host":
        resources_field_list = host_resources_field_list
    elif structure['subtype'] == "user":
        resources_field_list = user_resources_field_list
    else:
        resources_field_list = structures_resources_field_list

    for resource in resource_list:
        form_initial_data = {'name' : structure['name'], 'structure_type' : structure['subtype'], 'resource' : resource}

        for field in resources_field_list:
            if field in structure["resources"][resource]:
                editable_data += 1
                form_initial_data[field] = structure["resources"][resource][field]

        form_initial_data_list.append(form_initial_data)

    if structure['subtype'] == "host":
        HostResourcesFormSet = formset_factory(HostResourcesForm, extra = 0)
        structure['resources_form'] = HostResourcesFormSet(initial = form_initial_data_list)
        structure['resources_form_helper'] = HostResourcesFormSetHelper()
        submit_button_disp = 5
    elif structure['subtype'] == "user":
        UserResourcesFormSet = formset_factory(UserResourcesForm, extra = 0)
        structure['resources_form'] = UserResourcesFormSet(initial = form_initial_data_list)
        structure['resources_form_helper'] = UserResourcesFormSetHelper()
        submit_button_disp = 6
    else:
        StructureResourcesFormSet = formset_factory(StructureResourcesForm, extra = 0)
        structure['resources_form'] = StructureResourcesFormSet(initial = form_initial_data_list)
        structure['resources_form_helper'] = StructureResourcesFormSetHelper()
        submit_button_disp = 8

    structure['resources_form_helper'].form_action = form_action
    structure['resources_editable_data'] = editable_data

    ## Need to do this to hide extra 'Save changes' buttons on JS
    structure['resources_form_helper'].layout[submit_button_disp][0].name += structure['name']


def setLimitsForm(structure, form_action):
    editable_data = 0
    form_initial_data = {'name': structure['name']}
    resource_list = ["cpu", "mem", "disk_read", "disk_write", "net", "energy"]

    for resource in resource_list:
        for param in ["boundary", "boundary_type"]:
            value = structure.get('limits', {}).get(resource, {}).get(param, None)
            if value is not None:
                editable_data += 1
                form_initial_data[resource + '_' + param] = value

    structure['limits_form'] = LimitsForm(initial=form_initial_data)
    structure['limits_form'].helper.form_action = form_action
    structure['limits_editable_data'] = editable_data

    for resource in resource_list:
        for param in ["boundary", "boundary_type"]:
            if structure.get('limits', {}).get(resource, {}).get(param, None) is None:
                structure['limits_form'].helper[resource + '_' + param].update_attributes(type="hidden")


def setRemoveStructureForm(structures, form_action):

    removeStructuresForm = RemoveStructureForm()
    removeStructuresForm.helper.form_action = form_action

    for structure in structures:
        if form_action == "containers":
            removeStructuresForm.fields['selected_structures'].choices.append(((structure['name'],structure['host']),structure['name']))
        else:
            removeStructuresForm.fields['selected_structures'].choices.append((structure['name'],structure['name']))

    return removeStructuresForm


# ------------------------------------ Common functions for host management ------------------------------------

def getHostsNames(data):
    hosts = []
    for item in data:
        if item['subtype'] == 'host':
            hosts.append(item)

    hosts = sorted(hosts, key=functools.cmp_to_key(compareStructureNames))
    return hosts


def getHostFreeDiskLoad(host):
    free_disk_load = 0
    if 'disks' in host['resources']:
        for disk_name in host['resources']['disks']:
            disk = host['resources']['disks'][disk_name]
            free_disk_load += MAX_DISK_LOAD_DICT[disk['type']] - disk['load']

    return free_disk_load


def getFreestDisk(host):

    freest_disk = None

    ## Based on load
    # current_min_load = -1

    # disk_type_load_ratio = {}
    # for disk_type in MAX_DISK_LOAD_DICT:
    #     disk_type_load_ratio[disk_type] = MAX_DISK_LOAD_DICT["LVM"]/MAX_DISK_LOAD_DICT[disk_type]

    # if 'disks' in host['resources']:
    #     for disk_name in host['resources']['disks']:

    #         disk = host['resources']['disks'][disk_name]

    #         if disk['load'] == 0:
    #             freest_disk = disk_name
    #             break

    #         if (disk['load'] == MAX_DISK_LOAD_DICT[disk['type']]): continue

    #         adjusted_load = disk['load'] * disk_type_load_ratio[disk['type']]

    #         if current_min_load == -1 or adjusted_load < current_min_load:
    #             current_min_load = adjusted_load
    #             freest_disk = disk_name

    ## Based on Bandwidth
    current_max_bw = -1

    if 'disks' in host['resources']:
        for disk_name in host['resources']['disks']:

            disk = host['resources']['disks'][disk_name]

            ## Get combined free bandwidth
            consumed_read = disk["max_read"] - disk["free_read"]
            consumed_write = disk["max_write"] - disk["free_write"]
            total_max = max(disk["max_read"],disk["max_write"])
            total_free = total_max - consumed_read - consumed_write
            if (total_free == 0): continue

            ## TODO: think if it is better to assign a disk with no containers but low bandwidth or a contended disk with high bw
            if total_free == total_max:
                freest_disk = disk_name
                break

            if current_max_bw == -1 or total_free > current_max_bw:
                current_max_bw = total_free
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
        #         max_disk_usage += MAX_DISK_LOAD_DICT[disk['type']]
        #         disk_usage += disk['load']

        ## Based on bandwidth
        ## TODO: think if it is better to assign a disk with no containers but low bandwidth or a contended disk with high bw
        if 'disks' in host['resources']:
            for disk_name in host['resources']['disks']:
                disk = host['resources']['disks'][disk_name]
                consumed_read = disk["max_read"] - disk["free_read"]
                consumed_write = disk["max_write"] - disk["free_write"]
                total_max = max(disk["max_read"],disk["max_write"])
                total_free = total_max - consumed_read - consumed_write

                max_disk_usage += total_max
                disk_usage += total_free

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

    free_read_bw = 0
    free_write_bw = 0
    free_total_bw = 0

    if 'disks' in host['resources']:
        for disk_name in host['resources']['disks']:
            disk = host['resources']['disks'][disk_name]
            free_read_bw += disk['free_read']
            free_write_bw += disk['free_write']

            consumed_read = disk['max_read'] - disk['free_read']
            consumed_write = disk['max_write'] - disk['free_write']
            free_total_bw += max(disk['max_read'], disk['max_write']) - consumed_read - consumed_write

    return free_read_bw, free_write_bw, free_total_bw


# ------------------------------------ Common functions for app management ------------------------------------

def retrieve_global_hdfs_app(apps):
    global_hdfs_app = None
    namenode_container_info = None
    for app in apps:
        if app['name'] == "global_hdfs":
            global_hdfs_app = app
            break

    if global_hdfs_app:
        for container in global_hdfs_app['containers_full']:
            if 'namenode' in container['name']:
                namenode_container_info = container
                break

    return global_hdfs_app, namenode_container_info


def getDataAndFilterByApp(url, app_name):
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
    except urllib.error.HTTPError:
        data = {}

    for item in data:
        if item['subtype'] == 'application' and item['name'] == app_name:
            return data, item
    return data, None

def getContainersFromApp(data, app):
    return [item for item in data if item['subtype'] == 'container' and item['name'] in app['containers']]


def getAppFiles(app):
    return {
        'runtime_files': os.path.basename(app['runtime_files']),
        'output_dir': os.path.basename(app['output_dir']),
        'install_script': os.path.basename(app['install_script']),
        'start_script': os.path.basename(app['start_script']),
        'stop_script': os.path.basename(app['stop_script']),
        'app_jar': os.path.basename(app['app_jar']),
        'app_dir': os.path.dirname(app['start_script'])
    }