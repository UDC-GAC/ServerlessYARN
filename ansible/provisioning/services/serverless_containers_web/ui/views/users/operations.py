import functools

from ui.utils import SUPPORTED_RESOURCES

from ui.background_tasks import register_task, add_user_task, subscribe_apps_to_user, desubscribe_apps_from_user, remove_users_task

from ui.views.core.utils import getStructuresValuesLabels, getLimits, setStructureResourcesForm, setLimitsForm, compareStructureNames
from ui.views.users.utils import setAddAppToUserForm, setSubscriptionManagementForm, setAddUserForm


def getUsers(data, structures):
    # Associate apps with users or set as available
    available_apps, subscribed_apps = [], {}
    for structure in structures:
        if structure['subtype'] == 'application':
            app_subscribed = False
            for item in data:
                if item['subtype'] == 'user' and structure['name'] in item['clusters']:
                    subscribed_apps.setdefault(item['name'], []).append(structure)
                    app_subscribed = True
                    break
            if not app_subscribed:
                available_apps.append(structure)

    users = []
    for item in data:
        if item['subtype'] == 'user':
            user_apps = []
            for app in subscribed_apps.get(item['name'], []):
                app['limits'] = getLimits(app['name'])

                ## Container Resources Form
                setStructureResourcesForm(app,"users")

                ## Container Limits Form
                setLimitsForm(app, "users")

                ## Set labels for container values
                app['resources_values_labels'] = getStructuresValuesLabels(app, 'resources')
                app['limits_values_labels'] = getStructuresValuesLabels(app, 'limits')

                user_apps.append(app)

            item['apps_full'] = sorted(user_apps, key=functools.cmp_to_key(compareStructureNames))
            #item['limits'] = getLimits(item['name'])

            ## User Resources Form
            setStructureResourcesForm(item,"users")

            ## User Limits Form
            #setLimitsForm(item,"users")

            ## Set form to add apps to user
            setAddAppToUserForm(item, "apps")

            ## Set form to subscribe available apps to user
            setSubscriptionManagementForm(item, available_apps, "subscribe", "users")

            ## Set form to desubscribe apps from user
            setSubscriptionManagementForm(item, item['apps_full'], "desubscribe", "users")

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


def processSubscribeAppsToUser(request, url, **kwargs):
    error = ""
    task = subscribe_apps_to_user.delay(url, kwargs["structure_name"], kwargs["selected_structures"])
    print("Starting task with id {0}".format(task.id))

    register_task(task.id, "subscribe_apps_to_user")

    return error


def processDesubscribeAppsFromUser(request, url, **kwargs):
    error = ""
    task = desubscribe_apps_from_user.delay(url, kwargs["structure_name"], kwargs["selected_structures"])
    print("Starting task with id {0}".format(task.id))

    register_task(task.id, "desubscribe_apps_from_user")

    return error


def processRemoveUsers(request, url, **kwargs):
    task = remove_users_task.delay(url, kwargs["selected_structures"])
    print("Starting task with id {0}".format(task.id))
    register_task(task.id, "remove_users_task")