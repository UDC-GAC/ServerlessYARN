import time
import json
import urllib

from django.shortcuts import render, redirect
from django.conf import settings

from ui.background_tasks import get_pending_tasks_messages
from ui.utils import request_to_state_db


from ui.views.core.utils import redirect_with_errors, checkInvalidConfig
from ui.views.services.operations import processServiceConfigPost
from ui.views.services.utils import SERVICES_OPTIONS, SERVICES_FORMS

# ------------------------------------ Services views ------------------------------------

def services(request):
    url = settings.BASE_URL + "/service/"

    # Optional options based on config
    # Example -> if settings.PLATFORM_CONFIG['power_budgeting']: ...

    # If the request is a POST update corresponding service
    if len(request.POST) > 0:
        errors = []
        if "name" in request.POST:
            service_name = request.POST['name']
            for option in SERVICES_OPTIONS.get(service_name, []):
                error = processServiceConfigPost(request, url, service_name, option)
                if (len(error) > 0): errors.append(error)

        return redirect_with_errors('services', errors)

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    requests_errors = request.GET.getlist("errors", None)
    requests_successes = request.GET.getlist("success", None)
    requests_info = []

    ## Pending tasks
    still_pending_tasks, successful_tasks, failed_tasks = get_pending_tasks_messages()
    requests_errors.extend(failed_tasks)
    requests_successes.extend(successful_tasks)
    requests_info.extend(still_pending_tasks)

    ## get datetime in epoch to compare later with each service's heartbeat
    now = time.time()

    not_recognized_services = []
    for item in data_json:

        form_initial_data = {'name' : item['name']}
        editable_data = 0

        if item['name'] in SERVICES_OPTIONS and item['name'] in SERVICES_FORMS:
            for option in SERVICES_OPTIONS[item['name']]:
                if option.upper() in item['config']:
                    form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = SERVICES_FORMS[item['name']](**{"initial": form_initial_data})
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

    context = {
        'data': data_json,
        'config_errors': config_errors,
        'requests': {
            'errors': requests_errors,
            'successes': requests_successes,
            'info': requests_info
        },
        'config': settings.PLATFORM_CONFIG
    }

    return render(request, 'services.html', context)


def service_switch(request,service_name):

    state = request.POST['service_switch']

    ## send put to stateDatabase
    url = settings.BASE_URL + "/service/" + service_name + "/ACTIVE"

    if (state == "service_off"):
        activate = "false"
    else:
        activate = "true"

    put_field_data = {'value': activate}

    error_message = ""
    error, response = request_to_state_db(url, "put", error_message, put_field_data)
    if error: print(response.content) ## should not happen

    return redirect('services')


