from ui.forms import AddAppForm, AddUserForm, SubscribeAppForm, DesubscribeAppForm


def setAddAppToUserForm(user, form_action):
    addAppForm = AddAppForm()
    addAppForm.fields['user'].initial = user['name']
    addAppForm.fields['user'].widget.input_type = "hidden"
    addAppForm.helper.form_action = form_action

    user['add_app_form'] = addAppForm


def setSubscriptionManagementForm(user, apps, form_operation, form_action):
    form = None
    if form_operation == "subscribe":
        form = SubscribeAppForm()
    if form_operation == "desubscribe":
        form = DesubscribeAppForm()
    if form:
        form.fields['name'].initial = user['name']
        form.fields['name'].widget.input_type = "hidden"
        form.helper.form_action = form_action
        for app in apps:
            form.fields['selected_structures'].choices.append((app['name'], app['name']))

        user['{0}_app_form'.format(form_operation)] = form


def setAddUserForm():
    return {
        'user': AddUserForm()
    }