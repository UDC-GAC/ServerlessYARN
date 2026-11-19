## Access to the StateDatabase REST API
import json
import urllib

from django.conf import settings


def getDbData(url):

    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}

    return data_json


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


def getLimits(structure_name):
    url = settings.BASE_URL + "/structure/" + structure_name + "/limits"
    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}

    return data_json


def getScalerPollFreq():
    url = settings.BASE_URL + "/service/scaler"
    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())

    return data_json.get('config', {}).get('POLLING_FREQUENCY', 5)


def checkAppUser(app_name):
    url = settings.BASE_URL + "/user/"
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
    except urllib.error.HTTPError:
        data = {}

    for item in data:
        if app_name in item.get('clusters', []):
            return item['name']

    return None
