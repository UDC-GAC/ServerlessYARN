from django.shortcuts import render,redirect
from ui.forms import RuleForm, DBSnapshoterForm, GuardianForm, ScalerForm, StructuresSnapshoterForm, SanityCheckerForm, RefeederForm
from django.http import HttpResponse
import urllib.request
import json
import requests

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
def processServiceConfigPost(request, url, service_name, config_name):

    full_url = url + service_name + "/" + config_name.upper()
    headers = {'Content-Type': 'application/json'}

    json_fields = ["documents_persisted","guardable_resources","resources_persisted","generated_metrics"]

    new_value = request.POST[config_name]

    if (config_name in json_fields):
        ## JSON field request
        new_values_list = new_value.strip("[").strip("]").split(",")
        put_field_data = json.dumps({"value":[v.strip().strip('"') for v in new_values_list]})

        r = requests.put(full_url, data=put_field_data, headers=headers)

    else:
        ## Other field request
        put_field_data = {'value': new_value.lower()}

        r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    if (r.status_code == requests.codes.ok):
        print(r.content)
    else:
        pass

def services(request):
    url = base_url + "/service/"

    if (len(request.POST) > 0):

        if ("name" in request.POST):
            service_name = request.POST['name']

            if (service_name == 'database_snapshoter'):

                if ("debug" in request.POST):
                    processServiceConfigPost(request, url, service_name, "debug")

                if ("documents_persisted" in request.POST):
                    processServiceConfigPost(request, url, service_name, "documents_persisted")

                if ("polling_frequency" in request.POST):
                    processServiceConfigPost(request, url, service_name, "polling_frequency")

            if (service_name == 'guardian'):

                if ("cpu_shares_per_watt" in request.POST):
                    processServiceConfigPost(request, url, service_name, "cpu_shares_per_watt")

                if ("debug" in request.POST):
                    processServiceConfigPost(request, url, service_name, "debug")

                if ("event_timeout" in request.POST):
                    processServiceConfigPost(request, url, service_name, "event_timeout")

                if ("guardable_resources" in request.POST):
                    processServiceConfigPost(request, url, service_name, "guardable_resources")

                if ("structure_guarded" in request.POST):
                    processServiceConfigPost(request, url, service_name, "structure_guarded")

                if ("window_delay" in request.POST):
                    processServiceConfigPost(request, url, service_name, "window_delay")

                if ("window_timelapse" in request.POST):
                    processServiceConfigPost(request, url, service_name, "window_timelapse")

            if (service_name == 'scaler'):

                if ("check_core_map" in request.POST):
                    processServiceConfigPost(request, url, service_name, "check_core_map")

                if ("debug" in request.POST):
                    processServiceConfigPost(request, url, service_name, "debug")

                if ("polling_frequency" in request.POST):
                    processServiceConfigPost(request, url, service_name, "polling_frequency")

                if ("request_timeout" in request.POST):
                    processServiceConfigPost(request, url, service_name, "request_timeout")

            if (service_name == 'structures_snapshoter'):

                if ("polling_frequency" in request.POST):
                    processServiceConfigPost(request, url, service_name, "polling_frequency")

                if ("debug" in request.POST):
                    processServiceConfigPost(request, url, service_name, "debug")

                if ("persist_apps" in request.POST):
                    processServiceConfigPost(request, url, service_name, "persist_apps")

                if ("resources_persisted" in request.POST):
                    processServiceConfigPost(request, url, service_name, "resources_persisted")

            if (service_name == 'sanity_checker'):

                if ("debug" in request.POST):
                    processServiceConfigPost(request, url, service_name, "debug")

                if ("delay" in request.POST):
                    processServiceConfigPost(request, url, service_name, "delay")

            if (service_name == 'refeeder'):

                if ("debug" in request.POST):
                    processServiceConfigPost(request, url, service_name, "debug")

                if ("generated_metrics" in request.POST):
                    processServiceConfigPost(request, url, service_name, "generated_metrics")

                if ("polling_frequency" in request.POST):
                    processServiceConfigPost(request, url, service_name, "polling_frequency")

                if ("window_delay" in request.POST):
                    processServiceConfigPost(request, url, service_name, "window_delay")

                if ("window_timelapse" in request.POST):
                    processServiceConfigPost(request, url, service_name, "window_timelapse")

        return redirect('services')

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    #hosts = getHosts(data_json)
    

    for item in data_json:

        form_initial_data = {'name' : item['name']}
        editable_data = 0
        
        serviceForm = {}

        if (item['name'] == 'database_snapshoter'):
            if ('DEBUG' in item['config']): form_initial_data['debug'] = item['config']['DEBUG']
            if ('DOCUMENTS_PERSISTED' in item['config']): form_initial_data['documents_persisted'] = item['config']['DOCUMENTS_PERSISTED']
            if ('POLLING_FREQUENCY' in item['config']): form_initial_data['polling_frequency'] = item['config']['POLLING_FREQUENCY']
            editable_data += 1
            serviceForm = DBSnapshoterForm(initial = form_initial_data)

        elif (item['name'] == 'guardian'):
            if ('CPU_SHARES_PER_WATT' in item['config']): form_initial_data['cpu_shares_per_watt'] = item['config']['CPU_SHARES_PER_WATT']
            if ('DEBUG' in item['config']): form_initial_data['debug'] = item['config']['DEBUG']
            if ('EVENT_TIMEOUT' in item['config']): form_initial_data['event_timeout'] = item['config']['EVENT_TIMEOUT']
            if ('GUARDABLE_RESOURCES' in item['config']): form_initial_data['guardable_resources'] = item['config']['GUARDABLE_RESOURCES']
            if ('STRUCTURE_GUARDED' in item['config']): form_initial_data['structure_guarded'] = item['config']['STRUCTURE_GUARDED']
            if ('WINDOW_DELAY' in item['config']): form_initial_data['window_delay'] = item['config']['WINDOW_DELAY']
            if ('WINDOW_TIMELAPSE' in item['config']): form_initial_data['window_timelapse'] = item['config']['WINDOW_TIMELAPSE']
            editable_data += 1
            serviceForm = GuardianForm(initial = form_initial_data)

        elif (item['name'] == 'scaler'):
            if ('CHECK_CORE_MAP' in item['config']): form_initial_data['check_core_map'] = item['config']['CHECK_CORE_MAP']
            if ('DEBUG' in item['config']): form_initial_data['debug'] = item['config']['DEBUG']
            if ('POLLING_FREQUENCY' in item['config']): form_initial_data['polling_frequency'] = item['config']['POLLING_FREQUENCY']
            if ('REQUEST_TIMEOUT' in item['config']): form_initial_data['request_timeout'] = item['config']['REQUEST_TIMEOUT']
            editable_data += 1
            serviceForm = ScalerForm(initial = form_initial_data)

        if (item['name'] == 'structures_snapshoter'):
            if ('POLLING_FREQUENCY' in item['config']): form_initial_data['polling_frequency'] = item['config']['POLLING_FREQUENCY']
            if ('DEBUG' in item['config']): form_initial_data['debug'] = item['config']['DEBUG']
            if ('PERSIST_APPS' in item['config']): form_initial_data['persist_apps'] = item['config']['PERSIST_APPS']
            if ('RESOURCES_PERSISTED' in item['config']): form_initial_data['resources_persisted'] = item['config']['RESOURCES_PERSISTED']
            editable_data += 1
            serviceForm = StructuresSnapshoterForm(initial = form_initial_data)

        if (item['name'] == 'sanity_checker'):
            if ('DEBUG' in item['config']): form_initial_data['debug'] = item['config']['DEBUG']
            if ('DELAY' in item['config']): form_initial_data['delay'] = item['config']['DELAY']
            editable_data += 1
            serviceForm = SanityCheckerForm(initial = form_initial_data)

        if (item['name'] == 'refeeder'):
            if ('DEBUG' in item['config']): form_initial_data['debug'] = item['config']['DEBUG']
            if ('GENERATED_METRICS' in item['config']): form_initial_data['generated_metrics'] = item['config']['GENERATED_METRICS']
            if ('POLLING_FREQUENCY' in item['config']): form_initial_data['polling_frequency'] = item['config']['POLLING_FREQUENCY']
            if ('WINDOW_DELAY' in item['config']): form_initial_data['window_delay'] = item['config']['WINDOW_DELAY']
            if ('WINDOW_TIMELAPSE' in item['config']): form_initial_data['window_timelapse'] = item['config']['WINDOW_TIMELAPSE']
            editable_data += 1
            serviceForm = RefeederForm(initial = form_initial_data)

        item['form'] = serviceForm
        item['editable_data'] = editable_data

    return render(request, 'services.html', {'data': data_json})
    
def service_switch(request,service_name):

    state = request.POST['service_switch']

    ## send put to stateDatabase
    url = base_url + "/service/" + service_name + "/ACTIVE"

    if (state == "service_off"):
        activate = "false"
    else:
        activate = "true"

    headers = {'Content-Type': 'application/json'}

    put_field_data = {'value': activate}
    r = requests.put(url, data=json.dumps(put_field_data), headers=headers)

    if (r.status_code == requests.codes.ok):
        print(r.content)
    else:
        pass

    return redirect('services')

## Rules
def rules(request):
    url = base_url + "/rule/"

    if (len(request.POST) > 0):

        headers = {'Content-Type': 'application/json'}

        rule_name = request.POST['name']

        if ("amount" in request.POST):
            amount = request.POST['amount']
            put_field_data = {'value': amount}
        
            r = requests.put(url + rule_name + "/amount", data=json.dumps(put_field_data), headers=headers)

            if (r.status_code == requests.codes.ok):
                print(r.content)
            else:
                pass       

        return redirect('rules')


    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    rulesResources = getRulesResources(data_json)
    ruleTypes = ['requests','events']

    for item in data_json:
        item['rule_readable'] = jsonBooleanToHumanReadable(item['rule'])

        form_initial_data = {'name' : item['name']}
        editable_data = 0
        
        if ('amount' in item):
            editable_data += 1
            form_initial_data['amount'] = item['amount']

        ruleForm=RuleForm(initial = form_initial_data)

        if ('amount' not in item):
            ruleForm.helper['amount'].update_attributes(type="hidden")

        item['form'] = ruleForm
        item['editable_data'] = editable_data

    return render(request, 'rules.html', {'data': data_json, 'resources':rulesResources, 'types':ruleTypes})
    
def rule_switch(request,rule_name):

    state = request.POST['rule_switch']

    ## send put to stateDatabase
    url = base_url + "/rule/" + rule_name 

    if (state == "rule_off"):
        url += "/deactivate"
    else:
        url += "/activate"

    req = urllib.request.Request(url, method='PUT')
    #DATA=b'' 

    try:
        response = urllib.request.urlopen(req)
    except:
        pass

    return redirect('rules')

