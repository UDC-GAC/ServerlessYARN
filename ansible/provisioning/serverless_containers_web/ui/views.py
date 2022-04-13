from django.shortcuts import render
from django.http import HttpResponse
import urllib.request
import json

base_url = "http://192.168.56.100:5000"

## Auxiliary Methods
def getHosts(data):
    hosts = []

    for item in data:
         if (item['subtype'] == 'host'):
             containers = []
             for structure in data:
                 if (structure['subtype'] == 'container' and structure['host'] == item['name']):
                     structure['limits'] = getLimits(structure['name'])
                     containers.append(structure)
             item['containers'] = containers
             
             # Adjustment to don't let core_usage_mapping be too wide on html display
             if ("cpu" in item['resources'] and "core_usage_mapping" in item['resources']['cpu']):
                 item['resources']['cpu_cores'] = item['resources']['cpu']['core_usage_mapping']
                 item['resources']['cpu'] = {k:v for k,v in item['resources']['cpu'].items() if k != 'core_usage_mapping'}             
                              
             hosts.append(item)
                          
    return hosts

def getApps(data):
    apps = []

    for item in data:
         if (item['subtype'] == 'application'):
             containers = []
             for structure in data:
                 if (structure['subtype'] == 'container' and structure['name'] in item['containers']):
                     structure['limits'] = getLimits(structure['name'])
                     containers.append(structure)
             item['containers_full'] = containers
             item['limits'] = getLimits(item['name'])
             apps.append(item)        
    return apps

def getContainers(data):
    containers = []

    for item in data:
         if (item['subtype'] == 'container'):
             item['limits'] = getLimits(item['name'])
             containers.append(item)
    return containers

def getLimits(structure_name):
    url = base_url + "/structure/" + structure_name + "/limits"
    
    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    return data_json

def getRulesResources(data):
    resources = []
    
    for item in data:
        if (item['resource'] not in resources):
            resources.append(item['resource'])
    
    return resources

def jsonBooleanToHumanReadable(jsonBoolExpr):

    boolString = ""

    boolOperators = ['and','or','==','>=','<=','<','>']

    ## Check if dict or literal
    if type(jsonBoolExpr) is dict:
        firstElement = list(jsonBoolExpr.keys())[0]
    else:
        firstElement = jsonBoolExpr


    if (firstElement in boolOperators):
        ## Got bool expression
        jsonBoolValues = jsonBoolExpr[firstElement]
        for i in range(0, len(jsonBoolValues)):
            boolString += jsonBooleanToHumanReadable(jsonBoolValues[i])
            if (i < len(jsonBoolValues) - 1):
                boolString += " " + firstElement.upper() + " "

    elif (firstElement == 'var'):
        ## Got variable
        boolString = jsonBoolExpr[firstElement]

    else:
        ## Got literal
        boolString = str(firstElement)      

    return boolString


## Home
def index(request):
    url = base_url + "/heartbeat"
    
    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    return render(request, 'index.html', {'data': data_json})
    
## Structures
def structures(request):
    url = base_url + "/structure/"

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    return render(request, 'structures.html', {'data': data_json})
    
def structure_detail(request,structure_name):
    print(structure_name)
    url = base_url + "/structure/" + structure_name

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    return HttpResponse(json.dumps(data_json), content_type="application/json")

def containers(request):
    url = base_url + "/structure/"

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    containers = getContainers(data_json)
    
    return render(request, 'containers.html', {'data': containers})
    
def hosts(request):
    url = base_url + "/structure/"

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    hosts = getHosts(data_json)
    
    return render(request, 'hosts.html', {'data': hosts})

def apps(request):
    url = base_url + "/structure/"

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    apps = getApps(data_json)
    
    return render(request, 'apps.html', {'data': apps})

## Services
def services(request):
    url = base_url + "/service/"

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    #hosts = getHosts(data_json)
    
    return render(request, 'services.html', {'data': data_json})
    
## Rules
def rules(request):
    url = base_url + "/rule/"

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    rulesResources = getRulesResources(data_json)
    ruleTypes = ['requests','events']

    for item in data_json:
        item['rule_readable'] = jsonBooleanToHumanReadable(item['rule'])

    return render(request, 'rules.html', {'data': data_json, 'resources':rulesResources, 'types':ruleTypes})
    
