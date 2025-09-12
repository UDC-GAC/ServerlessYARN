import json
import urllib

from ui.forms import AddHostForm, AddDisksToHostsForm


def setAddHostForm(structures, structure_type):
    return {
        'host': AddHostForm(),
        'add_disks_to_hosts': setAddDisksToHostsForm(structures, structure_type)
    }


def setAddDisksToHostsForm(structures, form_action):
    addDisksToHostsForm = AddDisksToHostsForm()

    for host in structures:
        addDisksToHostsForm.fields['host_list'].choices.append((host['name'],host['name']))

    addDisksToHostsForm.helper.form_action = form_action

    return addDisksToHostsForm

def getContainersFromHost(url, host_name):
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
    except urllib.error.HTTPError:
        data = {}

    return [item for item in data if item['subtype'] == 'container' and item['host'] == host_name]