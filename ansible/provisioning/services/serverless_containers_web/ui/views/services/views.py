import time
import json
import urllib

from django.shortcuts import render, redirect
from django.conf import settings

from ui.background_tasks import get_pending_tasks_messages
from ui.utils import request_to_state_db
from ui.forms import DBSnapshoterForm, GuardianForm, ScalerForm, StructuresSnapshoterForm, SanityCheckerForm, RefeederForm, ReBalancerForm, WattTrainerForm, LimitsDispatcherForm, EnergyControllerForm

from ui.views.core.utils import redirect_with_errors, checkInvalidConfig
from ui.views.services.operations import processServiceConfigPost

# ------------------------------------ Services views ------------------------------------

def services(request):
    url = settings.BASE_URL + "/service/"
    # TODO: Split work in smaller functions and move to operations or utils
    database_snapshoter_options = ["debug","documents_persisted","polling_frequency"]
    guardian_options = ["debug", "event_timeout","guardable_resources","structure_guarded","window_delay","window_timelapse"]
    scaler_options = ["check_core_map","debug","polling_frequency","request_timeout"]
    structures_snapshoter_options = ["polling_frequency","debug","structures_persisted","resources_persisted"]
    sanity_checker_options = ["debug","delay"]
    refeeder_options = ["debug","structures_refeeded","generated_metrics","window_delay","window_timelapse"]
    rebalancer_options = ["debug","diff_percentage","stolen_percentage","window_delay","window_timelapse","resources_balanced","structures_balanced","containers_scope","balancing_policy","balancing_method","only_running"]
    watt_trainer_options = ["window_timelapse", "window_delay", "generated_metrics", "models_to_train", "debug"]
    limits_dispatcher_options = ["generated_metrics", "polling_frequency", "debug"]
    energy_controller_options = ["polling_frequency", "event_timeout", "window_timelapse", "window_delay", "debug", "structure_guarded", "control_policy", "power_model"]

    ## Optional options based on config
    # TODO: Remove this if Guardian is changed
    if settings.PLATFORM_CONFIG['power_budgeting']:
        guardian_options.extend(["energy_model_name", "use_energy_model"])

    # If the request is a POST update corresponding service
    if len(request.POST) > 0:
        if "name" in request.POST:
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

            elif (service_name == 'watt_trainer'):          options = watt_trainer_options

            elif (service_name == 'limits_dispatcher'):     options = limits_dispatcher_options

            elif (service_name == 'energy_controller'):     options = energy_controller_options

            for option in options:
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

        elif (item['name'] == 'watt_trainer'):
            for option in watt_trainer_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = WattTrainerForm(initial = form_initial_data)

        elif (item['name'] == 'limits_dispatcher'):
            for option in limits_dispatcher_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = LimitsDispatcherForm(initial = form_initial_data)

        elif (item['name'] == 'energy_controller'):
            for option in energy_controller_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = EnergyControllerForm(initial = form_initial_data)

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


