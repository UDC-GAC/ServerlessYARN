from ui.forms import AddAppForm, AddUserForm


def setAddAppToUserForm(user, form_action):
    addAppForm = AddAppForm()
    addAppForm.fields['user'].initial = user['name']
    addAppForm.fields['user'].widget.input_type = "hidden"
    addAppForm.helper.form_action = form_action

    user['add_app_form'] = addAppForm


def setAddUserForm():
    return {
        'user': AddUserForm()
    }