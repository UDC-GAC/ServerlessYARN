## Big Data (Hadoop / Spark / HDFS) specific forms

from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field
from crispy_forms.bootstrap import FormActions
from copy import deepcopy
from django.conf import settings
from ui.forms import DEFAULT_COMMON_FIELDS, AddAppForm, config
from ui.bigdata import SUPPORTED_FRAMEWORKS, DEFAULT_HDFS_VALUES

### Apps
class AddHadoopAppForm(AddAppForm):
    app_type = forms.CharField(label="App type", required=True, initial="hadoop_app")
    add_extra_framework = forms.BooleanField(label="Add additional framework?", required=False)
    framework = forms.ChoiceField(label="Additional framework",
            choices = (
                ("spark", "Spark"),
                ),
            required=False
            )

    def __init__(self, *args, **kwargs):
        super(AddHadoopAppForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-addhadoopappform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'apps'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('app_type', type="hidden", readonly=True),
            Field('name'),
            Field('cpu_max'),
            Field('cpu_min'),
            Field('cpu_weight'),
            Field('mem_max'),
            Field('mem_min'),
            Field('mem_weight')
        )

        if config['disk_capabilities'] and config['disk_scaling']:
            self.helper.layout.append(Field('disk_read_max'))
            self.helper.layout.append(Field('disk_read_min'))
            self.helper.layout.append(Field('disk_read_weight'))
            self.helper.layout.append(Field('disk_write_max'))
            self.helper.layout.append(Field('disk_write_min'))
            self.helper.layout.append(Field('disk_write_weight'))
        if config['power_budgeting']:
            self.helper.layout.append(Field('energy_max'))
            self.helper.layout.append(Field('energy_min'))
            self.helper.layout.append(Field('energy_weight'))

        # Boundaries and boundary types
        self.helper.layout.append(Field('cpu_boundary'))
        self.helper.layout.append(Field('cpu_boundary_type'))
        self.helper.layout.append(Field('mem_boundary'))
        self.helper.layout.append(Field('mem_boundary_type'))
        if config['disk_capabilities'] and config['disk_scaling']:
            self.helper.layout.append(Field('disk_read_boundary'))
            self.helper.layout.append(Field('disk_read_boundary_type'))
            self.helper.layout.append(Field('disk_write_boundary'))
            self.helper.layout.append(Field('disk_write_boundary_type'))
        if config['power_budgeting']:
            self.helper.layout.append(Field('energy_boundary'))
            self.helper.layout.append(Field('energy_boundary_type'))

        # Other parameters for application
        self.helper.layout.append(Field('app_dir'))
        self.helper.layout.append(Field('start_script'))
        self.helper.layout.append(Field('stop_script'))
        self.helper.layout.append(Field('add_install', css_class='add_install_condition'))
        self.helper.layout.append(Field('install_script', css_class='additional_install'))
        self.helper.layout.append(Field('add_install_files', css_class='add_install_files_condition'))
        self.helper.layout.append(Field('install_files', css_class='additional_install_files'))
        self.helper.layout.append(Field('add_runtime_files', css_class='add_runtime_files_condition'))
        self.helper.layout.append(Field('runtime_files', css_class='additional_runtime_files'))
        self.helper.layout.append(Field('add_output_dir', css_class='add_output_dir_condition'))
        self.helper.layout.append(Field('output_dir', css_class='additional_output_dir'))
        self.helper.layout.append(Field('add_extra_framework', css_class='add_extra_framework_condition'))
        self.helper.layout.append(Field('framework', css_class='framework'))

        # Submit button
        self.helper.layout.append(FormActions(Submit('save', 'Add app', css_class='caja')))


### Start apps
## The generic StartAppForm (check ui/forms.py) is extended with Big Data specific options
def get_global_hdfs_start_app_fields():
    """Fields to exchange data between Hadoop apps and the global HDFS (new instances on each call, as they are added to a single form)"""
    input_width = "500px"
    return {
        'read_from_global': forms.BooleanField(label="Read files from global HDFS?", required=False),
        'write_to_global': forms.BooleanField(label="Write files to global HDFS?", required=False),
        'global_input': forms.CharField(label="Input file (or directory) to read from global HDFS", required=False, 
            widget=forms.TextInput(attrs={'style': 'width: {0};'.format(input_width)})),
        'local_output': forms.CharField(label="Output directory to write to local HDFS (absolute or relative to '{0}')".format(DEFAULT_HDFS_VALUES["local_output"]), required=False, 
            widget=forms.TextInput(attrs={'style': 'width: {0};'.format(input_width)})),
        'local_input': forms.CharField(label="Input file (or directory) to read from local HDFS", required=False, 
            widget=forms.TextInput(attrs={'style': 'width: {0};'.format(input_width)})),
        'global_output': forms.CharField(label="Output directory to write to global HDFS (absolute or relative to '{0}')".format(DEFAULT_HDFS_VALUES["global_output"]), 
            required=False, widget=forms.TextInput(attrs={'style': 'width: {0};'.format(input_width)})),
    }

def add_global_hdfs_start_app_fields(start_app_form):
    """
    When the global HDFS is used in 'isolated' mode, allow:
      - Hadoop apps to read/write data from/to the global HDFS (fields are hidden by default, check set_bigdata_start_app_form)
      - Any app to wait for a Hadoop app to download/upload data from/to the global HDFS
    """
    if not (config['global_hdfs'] and config['hdfs_mode'] == 'isolated'):
        return

    start_app_form.fields['dependency_condition'].choices.append(("hdfs_downloading", "[HDFS] Downloading"))
    start_app_form.fields['dependency_condition'].choices.append(("hdfs_uploading", "[HDFS] Uploading"))

    start_app_form.fields.update(get_global_hdfs_start_app_fields())

    ## Add fields to the layout just before the submit button
    layout = start_app_form.helper.layout
    submit_index = next(i for i, layout_object in enumerate(layout.fields) if isinstance(layout_object, FormActions))
    for field in [
        Field('read_from_global', type="hidden", css_class='read_from_global_condition'),
        Field('global_input', css_class='global_input'),
        Field('local_output', css_class='local_output'),
        Field('write_to_global', type="hidden", css_class='write_to_global_condition'),
        Field('local_input', css_class='local_input'),
        Field('global_output', css_class='global_output'),
    ]:
        layout.insert(submit_index, field)
        submit_index += 1

def set_bigdata_start_app_form(structure):
    """Add the Big Data specific options to the form to start an app (structure['start_app_form'])"""
    start_app_form = structure['start_app_form']
    add_global_hdfs_start_app_fields(start_app_form)

    if settings.PLATFORM_CONFIG['global_hdfs'] and 'framework' in structure and structure['framework'] in SUPPORTED_FRAMEWORKS:
        start_app_form.helper['read_from_global'].update_attributes(type="show")
        start_app_form.helper['write_to_global'].update_attributes(type="show")

        ## Data locality allocation is only available for Hadoop apps, as they are the only ones exchanging data with the global HDFS
        assignation_policy_field = start_app_form.fields['assignation_policy']
        assignation_policy_field.choices = list(assignation_policy_field.choices) + [("Data-locality", "Data locality")]


### Global HDFS
class AddHdfsFileForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add_file"

    origin_path = forms.CharField(label= "Origin path of file or directory to upload (relative to {0})".format(config['global_hdfs_data_dir']),
            required=True
            )
    dest_path = forms.CharField(label= "Destination directory on the HDFS",
            required=True
            )

    def __init__(self, *args, **kwargs):
        super(AddHdfsFileForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-addhdfsfileform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'hdfs'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('origin_path'),
            Field('dest_path'),
            FormActions(
                Submit('save', 'Upload file/directory (put)', css_class='caja'),
            )
        )

class GetHdfsFileForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "get_file"

    origin_path = forms.CharField(label= "Origin path of file or directory to download from HDFS",
            required=True
            )
    dest_path = forms.CharField(label= "Destination directory (relative to {0})".format(config['global_hdfs_data_dir']),
            required=False
            )

    def __init__(self, *args, **kwargs):
        super(GetHdfsFileForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-gethdfsfileform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'hdfs'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('origin_path', readonly=True),
            Field('dest_path'),
            FormActions(
                Submit('save', 'Download file/directory (get)', css_class='caja'),
            )
        )

class AddHdfsDirForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add_dir"

    dest_path = forms.CharField(label= "Directory(es) to be created on the HDFS",
            required=True
            )

    def __init__(self, *args, **kwargs):
        super(AddHdfsDirForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-addhdfsdirform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'hdfs'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('dest_path'),
            FormActions(
                Submit('save', 'Add directory (mkdir -p)', css_class='caja'),
            )
        )

class DeleteHdfsFileForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "del_file"

    dest_path = forms.CharField(label= "File or directory path to be deleted on the HDFS",
            required=True
            )

    def __init__(self, *args, **kwargs):
        super(DeleteHdfsFileForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-deletehdfsfileform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'hdfs'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('dest_path', readonly=True),
            FormActions(
                Submit('save', 'Delete file/directory (rm)', css_class='caja'),
            )
        )
