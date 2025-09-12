import functools

from ui.utils import SUPPORTED_RESOURCES

from ui.background_tasks import register_task, add_user_task, remove_users_task

from ui.views.core.utils import getStructuresValuesLabels, getLimits, setStructureResourcesForm, setLimitsForm, compareStructureNames
from ui.views.users.utils import setAddAppToUserForm, setAddUserForm


def getUsers(data, structures):
    users = []
    for item in data:
        if item['subtype'] == 'user':
            apps = []
            for structure in structures:
                if structure['subtype'] == 'application' and structure['name'] in item['clusters']:
                    structure['limits'] = getLimits(structure['name'])

                    ## Container Resources Form
                    setStructureResourcesForm(structure,"users")

                    ## Container Limits Form
                    setLimitsForm(structure,"users")

                    ## Set labels for container values
                    structure['resources_values_labels'] = getStructuresValuesLabels(structure, 'resources')
                    structure['limits_values_labels'] = getStructuresValuesLabels(structure, 'limits')

                    apps.append(structure)

            item['apps_full'] = sorted(apps, key=functools.cmp_to_key(compareStructureNames))
            #item['limits'] = getLimits(item['name'])

            ## User Resources Form
            setStructureResourcesForm(item,"users")

            ## User Limits Form
            #setLimitsForm(item,"users")

            ## Set form to add apps to user
            setAddAppToUserForm(item, "apps")

            ## App RemoveAppFromUsersForm
            #setRemoveAppsFromUsersForm(item, containers, "apps")

            ## Set labels for users values
            item['resources_values_labels'] = getStructuresValuesLabels(item, 'resources')
            #item['limits_values_labels'] = getStructuresValuesLabels(item, 'limits')

            users.append(item)

    return users, setAddUserForm()


def processAddUser(request, url, **kwargs):
    full_url = url + "/" + kwargs["structure_name"]

    put_field_data = {
        'user': {
            ## Regular user data
            'name': kwargs["structure_name"],
            'resources': {},
            'type': "user",
            'subtype': "user"
        }
    }

    # Pure optional parameters
    for param in ['balancing_method']:
        if param in request.POST and request.POST[param] != "":
            put_field_data["user"][param] = request.POST[param]

    for resource in SUPPORTED_RESOURCES:
        if resource + "_max" in request.POST:
            resource_max = int(request.POST[resource + "_max"])
            resource_min = int(request.POST[resource + "_min"])
            put_field_data['user']['resources'][resource] = {'max': resource_max, 'min': resource_min}

    error = ""
    task = add_user_task.delay(full_url, put_field_data, kwargs["structure_name"])
    print("Starting task with id {0}".format(task.id))
    register_task(task.id, "add_user_task")

    return error


def processRemoveUsers(url, users):
    task = remove_users_task.delay(url, users)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id, "remove_users_task")