import json

from ui.forms import AddContainersForm


def setAddContainersForm(structures, hosts, form_action):

    host_list = {}
    for host in hosts:
        host_list[host['name']] = 0

    addContainersForm = AddContainersForm()
    addContainersForm.fields['host_list'].initial = json.dumps(host_list)
    addContainersForm.helper.form_action = form_action

    #addNContainersForm = setAddNContainersForm(structures,hosts,structure_type)

    return {
        "add_containers": addContainersForm,
        #"add_n_containers": addNContainersForm
    }
