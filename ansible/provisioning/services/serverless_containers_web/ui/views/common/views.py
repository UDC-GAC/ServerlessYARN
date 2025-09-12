import json
import urllib
from django.shortcuts import redirect
from django.http import HttpResponse
from django.conf import settings

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