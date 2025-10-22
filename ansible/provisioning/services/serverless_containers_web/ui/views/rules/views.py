
import json
import urllib

from django.conf import settings
from django.shortcuts import render, redirect

from ui.background_tasks import get_pending_tasks_messages
from ui.forms import RuleForm

from ui.views.core.utils import redirect_with_errors, checkInvalidConfig
from ui.views.rules.operations import processRulesPost
from ui.views.rules.utils import jsonBooleanToHumanReadable, getRulesResources

# ------------------------------------ Rules views ------------------------------------

def rules(request):
    url = settings.BASE_URL + "/rule/"

    if len(request.POST) > 0:
        errors = []
        rule_name = request.POST['name']
        rules_fields = ["amount","rescale_policy","up_events_required","down_events_required"]
        rules_fields_put_url = ["amount","policy","events_required","events_required"]
        rules_fields_dict = dict(zip(rules_fields, rules_fields_put_url))

        for field in rules_fields:
            if field in request.POST:
                error = processRulesPost(request, url, rule_name, field, rules_fields_dict[field])
                if len(error) > 0:
                    errors.append(error)

        return redirect_with_errors('rules',errors)

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

    for item in data_json:
        item['rule_readable'] = jsonBooleanToHumanReadable(item['rule'])

        form_initial_data = {'name' : item['name']}
        editable_data = 0

        if 'amount' in item:
            editable_data += 1
            form_initial_data['amount'] = item['amount']

        if 'rescale_policy' in item and item.get('rescale_type', "") == "up":
            editable_data += 1
            form_initial_data['rescale_policy'] = item['rescale_policy']

        rule_words = item['rule_readable'].split(" ")
        if 'events.scale.down' in rule_words:
            index = rule_words.index("events.scale.down")
            value = rule_words[index + 2]
            editable_data += 1
            form_initial_data['down_events_required'] = value

        if 'events.scale.up' in rule_words:
            index = rule_words.index("events.scale.up")
            value = rule_words[index + 2]
            editable_data += 1
            form_initial_data['up_events_required'] = value

        ruleForm=RuleForm(initial = form_initial_data)

        if 'amount' not in item:
            ruleForm.helper['amount'].update_attributes(type="hidden")

        if not ('rescale_policy' in item and item.get('rescale_type', "") == "up"):
            ruleForm.helper['rescale_policy'].update_attributes(type="hidden")

        if 'events.scale.down' not in rule_words:
            ruleForm.helper['down_events_required'].update_attributes(type="hidden")

        if 'events.scale.up' not in rule_words:
            ruleForm.helper['up_events_required'].update_attributes(type="hidden")

        item['form'] = ruleForm
        item['editable_data'] = editable_data

    rulesResources = getRulesResources(data_json)
    rulesResources.sort() # sort resources by alphabetical order
    ruleTypes = ['requests','events','']

    config_errors = checkInvalidConfig()

    context = {
        'data': data_json,
        'resources': rulesResources,
        'types': ruleTypes,
        'config_errors': config_errors,
        'requests': {
            'errors': requests_errors,
            'successes': requests_successes,
            'info': requests_info
        },
        'config': settings.PLATFORM_CONFIG
    }

    return render(request, 'rules.html', context)


def rule_switch(request,rule_name):
    state = request.POST['rule_switch']
    ## send put to stateDatabase
    url = settings.BASE_URL + "/rule/" + rule_name
    if state == "rule_off":
        url += "/deactivate"
    else:
        url += "/activate"

    req = urllib.request.Request(url, method='PUT')
    try:
        response = urllib.request.urlopen(req)
    except:
        pass

    return redirect('rules')

