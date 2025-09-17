import os
import json
import urllib
from django.conf import settings

# General utilities
from ui.utils import request_to_state_db

# Background tasks
from ui.background_tasks import get_pending_tasks_messages, register_task, remove_containers_from_app

# Views
from ui.views.core.utils import setRemoveStructureForm, getScalerPollFreq


def processStructures(request, structure_type, html_render, operations):
    users_url = settings.BASE_URL + "/user/"
    structures_url = settings.BASE_URL + "/structure/"
    url = users_url if structure_type == "users" else structures_url

    if len(request.POST) > 0:
        errors = []
        resources_errors = processResources(request)
        limits_errors = processLimits(request)
        operation_errors = processOperations(request, url, operations)

        if resources_errors: errors += resources_errors
        if limits_errors: errors += limits_errors
        if operation_errors: errors += operation_errors

        return None, None, None, errors

    requests_errors = request.GET.getlist("errors", None)
    requests_successes = request.GET.getlist("success", None)
    requests_info = []

    ## Pending tasks
    still_pending_tasks, successful_tasks, failed_tasks = get_pending_tasks_messages()
    requests_errors.extend(failed_tasks)
    requests_successes.extend(successful_tasks)
    requests_info.extend(still_pending_tasks)

    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}

    structures, addStructureForm = [], None
    if structure_type == "users":
        # Also get structures info to know which applications are subscribed to each user
        try:
            response = urllib.request.urlopen(structures_url)
            structures_json = json.loads(response.read())
        except urllib.error.HTTPError:
            structures_json = {}

        structures, addStructureForm = operations["get"](data_json, structures_json)
    else:
        structures, addStructureForm = operations["get"](data_json)



    ## Set RemoveStructures Form
    removeStructuresForm = setRemoveStructureForm(structures, structure_type)

    context = {
        'data': structures,
        'requests': {
            'errors': requests_errors,
            'successes': requests_successes,
            'info': requests_info
        },
        'addStructureForm': addStructureForm,
        'removeStructuresForm': removeStructuresForm,
        'config': settings.PLATFORM_CONFIG
    }

    return request, html_render, context, []


def processResources(request):
    structures_resources_field_list = ["guard","max","min","weight"]
    hosts_resources_field_list = ["max"]
    user_resources_field_list = ["max", "min"]
    errors = []
    if "form-TOTAL_FORMS" in request.POST:
        total_forms = int(request.POST['form-TOTAL_FORMS'])
        if total_forms > 0 and request.POST['form-0-operation'] == "resources":
            name = request.POST['form-0-name']
            url = settings.BASE_URL + "/structure/"
            if request.POST['form-0-structure_type'] == "host":
                resources_field_list = hosts_resources_field_list
            elif request.POST['form-0-structure_type'] == "user":
                url = settings.BASE_URL + "/user/"
                resources_field_list = user_resources_field_list
            else:
                resources_field_list = structures_resources_field_list

            for i in range(0,total_forms,1):
                resource = request.POST['form-' + str(i) + "-resource"]

                for field in resources_field_list:
                    field_value = request.POST['form-' + str(i) + "-" + field]
                    if field_value != "":
                        error = processResourcesFields(request, url, name, resource, field, field_value)
                        if len(error) > 0:
                            errors.append(error)

    return errors


def processResourcesFields(request, url, structure_name, resource, field, field_value):
    full_url = url + structure_name + "/resources/" + resource + "/"
    if field == "guard":
        if field_value == "True":
            full_url += "guard"
        else:
            full_url += "unguard"

        put_field_data = None

    else:
        full_url += field

        new_value = field_value
        put_field_data = {'value': new_value.lower()}

    error_message = "Error submitting {0} for structure {1}".format(field, structure_name)
    error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)

    return error


def processLimits(request):
    errors = []
    url = settings.BASE_URL + "/structure/"
    if "name" in request.POST and "operation" not in request.POST:
        structure_name = request.POST['name']
        resources = ["cpu", "mem", "disk_read", "disk_write", "net", "energy"]
        for resource in resources:
            if resource + "_boundary" in request.POST and resource + "_boundary_type" in request.POST:
                error = processLimitsBoundary(request, url, structure_name, resource)
                if len(error) > 0:
                    errors.append(error)
    return errors


def processLimitsBoundary(request, url, structure_name, resource):
    for param in ["boundary", "boundary_type"]:
        error = ""
        full_url = url + structure_name + "/limits/" + resource + "/" + param
        new_value = request.POST[resource + "_" + param]
        if new_value != '':
            put_field_data = {'value': new_value.lower()}
            error_message = "Error updating {0} for structure {1}".format(param, structure_name)
            error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)

    return error


def processOperations(request, url, operations):
    errors = []
    fallback = lambda *_, **__: "Operation not found"
    if "operation" in request.POST:
        kwargs = {
            "structure_name": request.POST.get("name", None),
            "host_list": request.POST.get('host_list', None),
            "selected_structures": request.POST.getlist('selected_structures', None)
        }

        error = operations.get(request.POST["operation"], fallback)(request, url, **kwargs)
        if error and len(error) > 0:
            errors.append(error)

    return errors
