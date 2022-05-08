from django.shortcuts import render,redirect
from ui.forms import RuleForm, DBSnapshoterForm, GuardianForm, ScalerForm, StructuresSnapshoterForm, SanityCheckerForm, RefeederForm, ReBalancerForm, LimitsForm, StructureResourcesForm, StructureResourcesFormSetHelper
from django.forms import formset_factory
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

                    ## Container Resources Form
                    setStructureResourcesForm(structure,"hosts")

                    ## Container Limits Form
                    setLimitsForm(structure,"hosts")

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

                    ## Container Resources Form
                    setStructureResourcesForm(structure,"apps")

                    ## Container Limits Form
                    setLimitsForm(structure,"apps")

                    containers.append(structure)

            item['containers_full'] = containers
            item['limits'] = getLimits(item['name'])

            ## App Resources Form
            setStructureResourcesForm(item,"apps")

            ## App Limits Form
            setLimitsForm(item,"apps")

            apps.append(item)
    return apps

def getContainers(data):
    containers = []

    for item in data:
        if (item['subtype'] == 'container'):
            item['limits'] = getLimits(item['name'])

            ## Container Resources Form
            setStructureResourcesForm(item,"containers")

            ## Container Limits Form
            setLimitsForm(item,"containers")

            containers.append(item)
    return containers

def setStructureResourcesForm(structure, form_action):

    editable_data = 0

    resource_list = ["cpu","mem"]
    resources_field_list = ["guard","max","min"]
    form_initial_data_list = []

    for resource in resource_list:
        form_initial_data = {'name' : structure['name'], 'resource' : resource}

        for field in resources_field_list:
            if (resource in structure["resources"] and field in structure["resources"][resource]):
                form_initial_data[field] = structure["resources"][resource][field]            

        form_initial_data_list.append(form_initial_data)

    StructureResourcesFormSet = formset_factory(StructureResourcesForm, extra = 0)

    editable_data += 1

    structure['resources_form'] = StructureResourcesFormSet(initial = form_initial_data_list)
    structure['resources_form_helper'] = StructureResourcesFormSetHelper()
    structure['resources_form_helper'].form_action = form_action
    structure['resources_editable_data'] = editable_data

    ## Need to do this to hide extra 'Save changes' buttons on JS
    structure['resources_form_helper'].layout[5][0].name += structure['name']
    

def setLimitsForm(structure, form_action):

    editable_data = 0
    form_initial_data = {'name' : structure['name']}

    resource_list = ["cpu","mem","disk","net","energy"]

    for resource in resource_list:
        if (resource in structure['limits'] and 'boundary' in structure['limits'][resource]): 
            form_initial_data[resource + '_boundary'] = structure['limits'][resource]['boundary']

    editable_data += 1
    structure['limits_form'] = LimitsForm(initial = form_initial_data)
    structure['limits_form'].helper.form_action = form_action
    structure['limits_editable_data'] = editable_data
    
def getLimits(structure_name):
    url = base_url + "/structure/" + structure_name + "/limits"
    
    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}
    
    
    return data_json

def getRulesResources(data):
    resources = []
    
    for item in data:
        if (item['resource'] not in resources):
            resources.append(item['resource'])
    
    return resources

def jsonBooleanToHumanReadable(jsonBoolExpr):

    boolString = ""

    boolOperators = ['and','or','==','>=','<=','<','>','+','-','*','/']

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

    if (len(request.POST) > 0):
        processResources(request, url)
        processLimits(request, url)
        return redirect('containers')

    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}
    
    containers = getContainers(data_json)
    
    return render(request, 'containers.html', {'data': containers})
    
def hosts(request):
    url = base_url + "/structure/"

    if (len(request.POST) > 0):
        processResources(request, url)
        processLimits(request, url)
        return redirect('hosts')

    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}
    
    hosts = getHosts(data_json)
    
    return render(request, 'hosts.html', {'data': hosts})

def apps(request):
    url = base_url + "/structure/"

    if (len(request.POST) > 0):
        processResources(request, url)
        processLimits(request, url)
        return redirect('apps')

    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}
    
    apps = getApps(data_json)
    
    return render(request, 'apps.html', {'data': apps})

def containers_guard_switch(request, container_name):

    guard_switch(request, container_name)
    return redirect("containers")

def hosts_guard_switch(request, container_name):

    guard_switch(request, container_name)
    return redirect("hosts")

def apps_guard_switch(request, container_name):

    guard_switch(request, container_name)
    return redirect("apps")

def guard_switch(request, container_name):

    state = request.POST['guard_switch']

    ## send put to stateDatabase
    url = base_url + "/structure/" + container_name 

    if (state == "guard_off"):
        url += "/unguard"
    else:
        url += "/guard"

    req = urllib.request.Request(url, method='PUT')
    #DATA=b'' 

    try:
        response = urllib.request.urlopen(req)
    except:
        pass

    return redirect('rules')

def processResources(request, url):

    resources_field_list = ["guard","max","min"]

    if ("form-TOTAL_FORMS" in request.POST):
        total_forms = int(request.POST['form-TOTAL_FORMS'])

        if (total_forms > 0):
            name = request.POST['form-0-name']

            for i in range(0,total_forms,1):
                resource = request.POST['form-' + str(i) + "-resource"]
    
                for field in resources_field_list:
                    field_value = request.POST['form-' + str(i) + "-" + field]
                    processResourcesFields(request, url, name, resource, field, field_value)

def processResourcesFields(request, url, structure_name, resource, field, field_value):

    full_url = url + structure_name + "/resources/" + resource + "/"

    if (field == "guard"):
        if (field_value == "True"): full_url += "guard"
        else:                       full_url += "unguard"
    
        r = requests.put(full_url)

    else:
        full_url += field
        headers = {'Content-Type': 'application/json'}

        new_value = field_value
        put_field_data = {'value': new_value.lower()}

        r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    if (r.status_code == requests.codes.ok):
        print(r.content)
    else:
        pass

def processLimits(request, url):
    if ("name" in request.POST):
        structure_name = request.POST['name']

        resources = ["cpu","mem","disk","net","energy"]

        for resource in resources:
            if (resource + "_boundary" in request.POST):
                processLimitsBoundary(request, url, structure_name, resource, resource + "_boundary")

def processLimitsBoundary(request, url, structure_name, resource, boundary_name):

    full_url = url + structure_name + "/limits/" + resource + "/boundary"
    headers = {'Content-Type': 'application/json'}

    new_value = request.POST[boundary_name]
    put_field_data = {'value': new_value.lower()}

    r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    if (r.status_code == requests.codes.ok):
        print(r.content)
    else:
        pass

## Services
def processServiceConfigPost(request, url, service_name, config_name):

    full_url = url + service_name + "/" + config_name.upper()
    headers = {'Content-Type': 'application/json'}

    json_fields = ["documents_persisted"]
    multiple_choice_fields = ["guardable_resources","resources_persisted","generated_metrics"]

    if (config_name in json_fields):
        ## JSON field request
        new_value = request.POST[config_name]
        new_values_list = new_value.strip("[").strip("]").split(",")
        put_field_data = json.dumps({"value":[v.strip().strip('"') for v in new_values_list]})

        r = requests.put(full_url, data=put_field_data, headers=headers)

    elif (config_name in multiple_choice_fields):
        ## MultipleChoice field request
        new_values_list = request.POST.getlist(config_name)
        put_field_data = json.dumps({"value":[v.strip().strip('"') for v in new_values_list]})

        r = requests.put(full_url, data=put_field_data, headers=headers)

    else:
        ## Other field request
        new_value = request.POST[config_name]
        
        put_field_data = {'value': new_value.lower()}
        r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    if (r.status_code == requests.codes.ok):
        print(r.content)
    else:
        pass

def services(request):
    url = base_url + "/service/"

    database_snapshoter_options = ["debug","documents_persisted","polling_frequency"]
    guardian_options = ["cpu_shares_per_watt", "debug", "event_timeout","guardable_resources","structure_guarded","window_delay","window_timelapse"]
    scaler_options = ["check_core_map","debug","polling_frequency","request_timeout"]
    structures_snapshoter_options = ["polling_frequency","debug","persist_apps","resources_persisted"]
    sanity_checker_options = ["debug","delay"]
    refeeder_options = ["debug","generated_metrics","polling_frequency","window_delay","window_timelapse"]
    rebalancer_options = ["debug","rebalance_users","energy_diff_percentage","energy_stolen_percentage","window_delay","window_timelapse"]

    if (len(request.POST) > 0):
        if ("name" in request.POST):
            service_name = request.POST['name']

            options = []

            if (service_name == 'database_snapshoter'):     options = database_snapshoter_options

            elif (service_name == 'guardian'):              options = guardian_options

            elif (service_name == 'scaler'):                options = scaler_options

            elif (service_name == 'structures_snapshoter'): options = structures_snapshoter_options

            elif (service_name == 'sanity_checker'):        options = sanity_checker_options

            elif (service_name == 'refeeder'):              options = refeeder_options

            elif (service_name == 'rebalancer'):            options = rebalancer_options

            for option in options:
                if (option in request.POST):
                    processServiceConfigPost(request, url, service_name, option)

        return redirect('services')

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    #hosts = getHosts(data_json)
    

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

        if (item['name'] == 'structures_snapshoter'):
            for option in structures_snapshoter_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = StructuresSnapshoterForm(initial = form_initial_data)

        if (item['name'] == 'sanity_checker'):
            for option in sanity_checker_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = SanityCheckerForm(initial = form_initial_data)

        if (item['name'] == 'refeeder'):
            for option in refeeder_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = RefeederForm(initial = form_initial_data)

        if (item['name'] == 'rebalancer'):
            for option in rebalancer_options:
                if (option.upper() in item['config']): form_initial_data[option] = item['config'][option.upper()]

            editable_data += 1
            serviceForm = ReBalancerForm(initial = form_initial_data)

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

        rule_name = request.POST['name']
        rules_fields = ["amount","rescale_policy","up_events_required","down_events_required"]
        rules_fields_put_url = ["amount","policy","events_required","events_required"]
        rules_fields_dict = dict(zip(rules_fields, rules_fields_put_url))

        for field in rules_fields:
            if (field in request.POST):
                processRulesPost(request, url, rule_name, field, rules_fields_dict[field])

        return redirect('rules')

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())
    
    rulesResources = getRulesResources(data_json)
    ruleTypes = ['requests','events','']

    for item in data_json:
        item['rule_readable'] = jsonBooleanToHumanReadable(item['rule'])

        form_initial_data = {'name' : item['name']}
        editable_data = 0
        
        if ('amount' in item):
            editable_data += 1
            form_initial_data['amount'] = item['amount']

        if ('rescale_policy' in item and 'rescale_type' in item and item['rescale_type'] == "up"):
            editable_data += 1
            form_initial_data['rescale_policy'] = item['rescale_policy']

        rule_words = item['rule_readable'].split(" ")
        if ('events.scale.down' in rule_words):
            index = rule_words.index("events.scale.down")
            value = rule_words[index + 2]
            editable_data += 1
            form_initial_data['up_events_required'] = value

        if ('events.scale.up' in rule_words):
            index = rule_words.index("events.scale.up")
            value = rule_words[index + 2]
            editable_data += 1
            form_initial_data['down_events_required'] = value

        ruleForm=RuleForm(initial = form_initial_data)

        editable_data += 1
        #if ('amount' not in item):
        #    ruleForm.helper['amount'].update_attributes(type="hidden")

        if (not ('rescale_policy' in item and 'rescale_type' in item and item['rescale_type'] == "up")):
            ruleForm.helper['rescale_policy'].update_attributes(type="hidden")

        if ('events.scale.down' not in rule_words):
            ruleForm.helper['down_events_required'].update_attributes(type="hidden")

        if ('events.scale.up' not in rule_words):    
            ruleForm.helper['up_events_required'].update_attributes(type="hidden")

        item['form'] = ruleForm
        item['editable_data'] = editable_data

    return render(request, 'rules.html', {'data': data_json, 'resources':rulesResources, 'types':ruleTypes})

def processRulesPost(request, url, rule_name, field, field_put_url):

    full_url = url + rule_name + "/" + field_put_url
    headers = {'Content-Type': 'application/json'}

    new_value = request.POST[field]
    put_field_data = {'value': new_value}

    if (field_put_url == "events_required"):
        if (field == "up_events_required"):
            event_type = "up"
        else:
            event_type = "down"

        put_field_data['event_type'] = event_type
             
    r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    if (r.status_code == requests.codes.ok):
        print(r.content)
    else:
        pass 

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
