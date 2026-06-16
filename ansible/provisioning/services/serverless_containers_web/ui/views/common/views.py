import json
import urllib
import logging
from datetime import datetime
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings

from ui.views.apps.operations import processStartApp, processStopApp
from ui.background_tasks import remove_task, create_artificial_task, update_task_runtime, get_app_counter, create_app_counter, remove_app_counter

# ------------------------------------ Common views across all endpoints ------------------------------------

def structure_detail(request, structure_name, structure_type):
    url = settings.BASE_URL + "/" + structure_type + "/" + structure_name
    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    return HttpResponse(json.dumps(data_json), content_type="application/json")


def remove_pending_task(request, alert_id):
    remove_task(alert_id)
    return_page = request.POST.get('next', '/')
    return redirect(return_page)


def api_start_app(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    error = processStartApp(request, settings.BASE_URL + "/structure/", structure_name=request.POST.get("name"))
    if error:
        return JsonResponse({"success": False, "error": error}, status=400)

    return JsonResponse({"success": True})


def api_stop_app(request, structure_name):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    ## Retrieve exit info
    runtime = "{:.2f}".format(float(request.POST.get("runtime", 0)))
    exit_code = int(request.POST.get("exit_code", -1))
    container = request.META.get("HTTP_X_SENDER_HOST") ## Django <= 2.1 ; Django 2.1+ would use 'request.headers'

    ## Classify status based on exit code
    if exit_code == 0:
        status = "SUCCESS"
        result = None
    elif exit_code > 0:
        status = "FAILURE"
        result = Exception(f"Exit code: {exit_code}")
    else:
        status = None
        result = None

    ## Create fake task to show on notification system on page reload
    task_name = f"{structure_name}-{container}" if container is not None else structure_name
    task_id = create_artificial_task(task_name=task_name, status=status, result=result)
    update_task_runtime(task_id, runtime)

    ## Also send exit info to celery log (useful for debugging)
    logging.basicConfig(
        level=logging.INFO,
        filename=f"../celery/celery_{datetime.today().strftime('%d-%m-%y')}.log",
        filemode="a",
        format = '\n%(asctime)s - %(levelname)s - APP FINISHED \n%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.info(f"{'#'*80}\nAPP [{structure_name} ({container})] has finished with {runtime} seconds and exit code {exit_code}\n{'#'*80}\n")

    ## Check counter for active containers; only stop app if this is the last container
    active_containers = get_app_counter(structure_name)
    if active_containers and int(active_containers) > 1:
        active_containers = int(active_containers) - 1
        create_app_counter(structure_name, active_containers)
    else:
        remove_app_counter(structure_name)
        error = processStopApp(settings.BASE_URL + "/structure/", structure_name=structure_name)
        if error:
            return JsonResponse({"success": False, "error": error}, status=400)

    return JsonResponse({"success": True})