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


def processStructures(request, structure_type, html_render, add_operation, rm_operation, get_operation):
    users_url = settings.BASE_URL + "/user/"
    structures_url = settings.BASE_URL + "/structure/"
    url = users_url if structure_type == "users" else structures_url

    if len(request.POST) > 0:
        errors = []
        resources_errors = processResources(request, url)
        limits_errors = processLimits(request, url)
        add_errors = processAdds(request, url, add_operation)
        removes_errors = processRemoves(request, url, rm_operation)

        if resources_errors: errors += resources_errors
        if limits_errors: errors += limits_errors
        if add_errors: errors += add_errors
        if removes_errors: errors += removes_errors

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

        structures, addStructureForm = get_operation(data_json, structures_json)
    else:
        structures, addStructureForm = get_operation(data_json)



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


def processResources(request, url):
    structures_resources_field_list = ["guard","max","min","weight"]
    hosts_resources_field_list = ["max"]
    user_resources_field_list = ["max", "min"]
    errors = []
    if "form-TOTAL_FORMS" in request.POST:
        total_forms = int(request.POST['form-TOTAL_FORMS'])
        if total_forms > 0 and request.POST['form-0-operation'] == "resources":
            name = request.POST['form-0-name']
            if request.POST['form-0-structure_type'] == "host":
                resources_field_list = hosts_resources_field_list
            elif request.POST['form-0-structure_type'] == "user":
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


def processLimits(request, url):
    errors = []
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


def processAdds(request, url, add_operation):
    errors = []
    if "operation" in request.POST and request.POST["operation"] == "add":
        kwargs = {
            "structure_name": request.POST.get("name", None),
            "host_list": request.POST.get('host_list', None),
        }
        error = add_operation(request, url, **kwargs)

        if error and len(error) > 0:
            errors.append(error)

    return errors


def processRemoves(request, url, rm_operation):
    errors = []
    if "operation" in request.POST and request.POST["operation"] == "remove":
        if "structures_removed" in request.POST:
            structures_to_remove = request.POST.getlist('structures_removed', None)
            error = rm_operation(url, structures_to_remove)
            if error and len(error) > 0:
                errors.append(error)

        elif "containers_removed" in request.POST:
            ## Remove containers from app scenario
            containers_to_remove = request.POST.getlist('containers_removed', None)
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

            error = processRemoveContainersFromApp(url, containers_to_remove, app, app_files)
            if len(error) > 0:
                errors.append(error)

    return errors


def processRemoveContainersFromApp(url, container_host_duples, app, app_files):
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