from ui.forms import StartAppForm, RemoveContainersFromAppForm, AddAppForm
from ui.bigdata.forms import AddHadoopAppForm, set_bigdata_start_app_form


def setStartAppForm(structure, form_action, started_app):
    startAppForm = StartAppForm()
    startAppForm.fields['name'].initial = structure['name']
    startAppForm.helper.form_action = form_action

    structure['start_app_form'] = startAppForm
    structure['started_app'] = started_app

    ## Big Data specific options (e.g., read/write data from/to the global HDFS)
    set_bigdata_start_app_form(structure)

def setAddAppForm():
    return {
        'app': AddAppForm(),
        'hadoop_app': AddHadoopAppForm()
    }

def setRemoveContainersFromAppForm(app, containers, form_action):
    removeContainersFromAppForm = RemoveContainersFromAppForm()
    removeContainersFromAppForm.fields['app'].initial = app['name']
    removeContainersFromAppForm.fields['runtime_files'].initial = app['runtime_files']
    removeContainersFromAppForm.fields['output_dir'].initial = app['output_dir']
    removeContainersFromAppForm.fields['install_script'].initial = app['install_script']
    removeContainersFromAppForm.fields['start_script'].initial = app['start_script']
    removeContainersFromAppForm.fields['stop_script'].initial = app['stop_script']

    removeContainersFromAppForm.helper.form_action = form_action

    editable_data = 0
    for container in containers:
        editable_data += 1
        disk_path = ""
        if 'disk' in container['resources']:
            disk_path = container['resources']['disk']['path']
        removeContainersFromAppForm.fields['selected_structures'].choices.append(((container['name'],container['host'],disk_path),container['name']))

    app['remove_containers_from_app_form'] = removeContainersFromAppForm
    app['remove_containers_from_app_editable_data'] = editable_data
