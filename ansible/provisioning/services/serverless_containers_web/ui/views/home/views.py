import json
import urllib

from django.shortcuts import render
from django.conf import settings


# ------------------------------------ Home views ------------------------------------

def index(request):
    url = settings.BASE_URL + "/heartbeat"
    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.URLError:
        data_json = {"status": "down"}

    return render(request, 'index.html', {'data': data_json, 'config': settings.PLATFORM_CONFIG})

