import json
import urllib
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings

from ui.views.apps.operations import processStartApp, processStopApp
from ui.background_tasks import remove_task

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

    error = processStopApp(settings.BASE_URL + "/structure/", structure_name=structure_name)
    if error:
        return JsonResponse({"success": False, "error": error}, status=400)

    return JsonResponse({"success": True})