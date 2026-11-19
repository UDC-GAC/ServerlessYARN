import os
import json
import urllib

from django.forms import formset_factory
from django.shortcuts import redirect
from django.conf import settings

from ui.utils import EXCLUDED_VALUES_LABELS
from ui.forms import LimitsForm, StructureResourcesForm, StructureResourcesFormSetHelper, HostResourcesForm, HostResourcesFormSetHelper, UserResourcesForm, UserResourcesFormSetHelper, RemoveStructureForm


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
        if key not in ["cpu_cores", "disks", "disk"]:
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


# ------------------------------------ Common functions for app management ------------------------------------

def retrieve_app(apps, app_name):
    found_app = None

    for app in apps:
        if app['name'] == app_name:
            found_app = app
            break

    return found_app

def retrieve_global_hdfs_app(apps):
    namenode_container_info = None
    datanodes = []
    global_hdfs_app = retrieve_app(apps, settings.VARS_CONFIG['global_hdfs_app_name'])

    if global_hdfs_app:
        for container in global_hdfs_app['containers_full']:
            if 'namenode' in container['name']:
                namenode_container_info = container
            elif 'datanode' in container['name']:
                datanodes.append(container)

    return global_hdfs_app, namenode_container_info, datanodes


def getContainersFromApp(data, app):
    return [item for item in data if item['subtype'] == 'container' and item['name'] in app['containers']]


def getAppFiles(app):
    return {
        'runtime_files': os.path.basename(app['runtime_files']),
        'output_dir': os.path.basename(app['output_dir']),
        'install_script': os.path.basename(app['install_script']),
        'start_script': os.path.basename(app['start_script']),
        'stop_script': os.path.basename(app['stop_script']),
        'app_dir': os.path.dirname(app['start_script'])
    }