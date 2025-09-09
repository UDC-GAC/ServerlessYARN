from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, ButtonHolder, Field, Button
from crispy_forms.bootstrap import FormActions
from django_json_widget.widgets import JSONEditorWidget
import yaml
from copy import deepcopy
from ui.utils import DEFAULT_APP_VALUES, DEFAULT_LIMIT_VALUES, DEFAULT_RESOURCE_VALUES, DEFAULT_HDFS_VALUES, DEFAULT_SERVICE_PARAMETERS

config_path = "../../config/config.yml"
with open(config_path, "r") as config_file:
    config = yaml.load(config_file, Loader=yaml.FullLoader)

DEFAULT_COMMON_FIELDS = {
        ## Basic fields
        'operation': forms.CharField(label= "Operation", required=True),
        'structure_type': forms.CharField(label= "Structure type", required=True),
        'name': forms.CharField(label="Name", required=True),

        ## Resource limits
        'cpu_max': forms.IntegerField(label="CPU Max", required=True, min_value=1),
        'cpu_min': forms.IntegerField(label="CPU Min", required=True, min_value=1),
        'cpu_weight': forms.IntegerField(label="CPU Weight ({0} if unset)".format(DEFAULT_RESOURCE_VALUES["weight"]), required=False, min_value=1, max_value=100),
        'mem_max': forms.IntegerField(label="Mem Max", required=True, min_value=1),
        'mem_min': forms.IntegerField(label="Mem Min", required=True, min_value=1),
        'mem_weight': forms.IntegerField(label="Mem Weight ({0} if unset)".format(DEFAULT_RESOURCE_VALUES["weight"]), required=False, min_value=1, max_value=100),
        'disk_read_max': forms.IntegerField(label="Disk Read I/O Bandwidth Max", required=True, min_value=1),
        'disk_read_min': forms.IntegerField(label="Disk Read I/O Bandwidth Min", required=True, min_value=1),
        'disk_read_weight': forms.IntegerField(label="Disk Read I/O Bandwidth Weight ({0} if unset)".format(DEFAULT_RESOURCE_VALUES["weight"]), required=False, min_value=1, max_value=100),
        'disk_write_max': forms.IntegerField(label="Disk Write I/O Bandwidth Max", required=True, min_value=1),
        'disk_write_min': forms.IntegerField(label="Disk Write I/O Bandwidth Min", required=True, min_value=1),
        'disk_write_weight': forms.IntegerField(label="Disk Write I/O Bandwidth Weight ({0} if unset)".format(DEFAULT_RESOURCE_VALUES["weight"]), required=False, min_value=1, max_value=100),
        'energy_max': forms.IntegerField(label="Energy Max", required=False, min_value=1),
        'energy_min': forms.IntegerField(label="Energy Min", required=False, min_value=1),
        'energy_weight': forms.IntegerField(label="Energy Weight ({0} if unset)".format(DEFAULT_RESOURCE_VALUES["weight"]), required=False, min_value=1, max_value=100),

        ## Resource boundaries
        'cpu_boundary': forms.IntegerField(label="CPU boundary ({0}% if unset)".format(DEFAULT_LIMIT_VALUES["boundary"]), required=False, min_value=1, max_value=100),
        'mem_boundary': forms.IntegerField(label="Mem boundary ({0}% if unset)".format(DEFAULT_LIMIT_VALUES["boundary"]), required=False, min_value=1, max_value=100),
        'disk_read_boundary': forms.IntegerField(label="Disk read boundary ({0}% if unset)".format(DEFAULT_LIMIT_VALUES["boundary"]), required=False, min_value=1, max_value=100),
        'disk_write_boundary': forms.IntegerField(label="Disk write boundary ({0}% if unset)".format(DEFAULT_LIMIT_VALUES["boundary"]), required=False, min_value=1, max_value=100),
        'energy_boundary': forms.IntegerField(label="Energy boundary ({0}% if unset)".format(DEFAULT_LIMIT_VALUES["boundary"]), required=False, min_value=1, max_value=100),

        # Resource boundary types
        'cpu_boundary_type': forms.ChoiceField(label="CPU boundary type (percentage of max or current)",
                                               choices=(
                                                   ("percentage_of_max", "Percentage of max"),
                                                   ("percentage_of_current", "Percentage of current"),
                                               ),
                                               required=False),
        'mem_boundary_type': forms.ChoiceField(label="Mem boundary type (percentage of max or current)",
                                               choices=(
                                                   ("percentage_of_max", "Percentage of max"),
                                                   ("percentage_of_current", "Percentage of current"),
                                               ),
                                               required=False),
        'disk_read_boundary_type': forms.ChoiceField(label="Disk read boundary type (percentage of max or current)",
                                               choices=(
                                                   ("percentage_of_max", "Percentage of max"),
                                                   ("percentage_of_current", "Percentage of current"),
                                               ),
                                               required=False),
        'disk_write_boundary_type': forms.ChoiceField(label="Disk write boundary type (percentage of max or current)",
                                               choices=(
                                                   ("percentage_of_max", "Percentage of max"),
                                                   ("percentage_of_current", "Percentage of current"),
                                               ),
                                               required=False),
        'energy_boundary_type': forms.ChoiceField(label="Energy boundary type (percentage of max or current)",
                                               choices=(
                                                   ("percentage_of_max", "Percentage of max"),
                                                   ("percentage_of_current", "Percentage of current"),
                                               ),
                                               required=False),

        ## Application files
        # 'add_files_dir': forms.BooleanField(label="Add additional files directory?", required=False),
        # 'files_dir': forms.CharField(label="Files directory ('{0}' if unset)".format(DEFAULT_APP_VALUES['files_dir']), required=False),
        'add_install': forms.BooleanField(label="Add install script?", required=False),
        'install_script': forms.CharField(label="Install script ('{0}' if unset)".format(DEFAULT_APP_VALUES['install_script']), required=False),
        'add_install_files': forms.BooleanField(label="Add additional files directory for installation?", required=False),
        'install_files': forms.CharField(label="Install files directory ('{0}' if unset)".format(DEFAULT_APP_VALUES['install_files']), required=False),
        'add_runtime_files': forms.BooleanField(label="Add additional files directory for runtime?", required=False),
        'runtime_files': forms.CharField(label="Runtime files directory ('{0}' if unset)".format(DEFAULT_APP_VALUES['runtime_files']), required=False),
        'add_output_dir': forms.BooleanField(label="Add directory to store output data?", required=False),
        'output_dir': forms.CharField(label="Output directory ('{0}' if unset)".format(DEFAULT_APP_VALUES['output_dir']), required=False),
        'start_script': forms.CharField(label="Start script ('{0}' if unset)".format(DEFAULT_APP_VALUES['start_script']), required=False),
        'stop_script': forms.CharField(label="Stop script ('{0}' if unset)".format(DEFAULT_APP_VALUES['stop_script']), required=False),

        ## Services
        'debug': forms.ChoiceField(label="Debug",
                choices=(
                        ("True", "True"),
                        ("False", "False"),
                ),
                required=True
        ),
        'polling_frequency': forms.IntegerField(label="Polling Frequency (seconds)", required=True, min_value=1),
        'window_delay': forms.IntegerField(label="Window Delay (seconds)", required=True, min_value=1),
        'window_timelapse': forms.IntegerField(label="Window Timelapse (seconds)", required=True, min_value=1),

}

### Structures
class HostResourcesFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = 'post'
        self.form_id = 'id-hostresourcesForm'
        self.form_class = 'form-group'
        self.form_method = 'post'
        self.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('name', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('resource', readonly=True),
            Field('max'),
            FormActions(
                Submit('save-resources-', 'Save changes', css_class='caja'),
            )
        )
        self.render_required_fields = True

class HostResourcesForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "resources"
    name = common_fields['name']

    structure_type = forms.ChoiceField(label="Type",
            choices = (
                ("application", "Application"),
                ("container", "Container"),
                ("host", "Host"),
                ),
            initial="host",
            required=True
            )
    resource = forms.CharField(label="Resource",
            required=True
            )
    max = forms.IntegerField(label="Maximum",
            required=True
            )

class StructureResourcesFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = 'post'
        self.form_id = 'id-structureresourcesForm'
        self.form_class = 'form-group'
        self.form_method = 'post'
        self.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('name', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('resource', readonly=True),
            Field('guard'),
            Field('max'),
            Field('min'),
            Field('weight'),
            FormActions(
                Submit('save-resources-', 'Save changes', css_class='caja'),
            )
        )
        self.render_required_fields = True

class StructureResourcesForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "resources"
    name = common_fields['name']

    resource = forms.CharField(label="Resource",
            required=True
            )
    structure_type = forms.ChoiceField(label="Type",
            choices = (
                ("application", "Application"),
                ("container", "Container"),
                ("host", "Host"),
                ),
            required=True
            )

    guard = forms.ChoiceField(label="Guard",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=True
            )
    max = forms.IntegerField(label="Maximum",
            required=True
            )
    min = forms.IntegerField(label="Minimum",
            required=True
            )
    weight = forms.IntegerField(label="Weight",
            required=False
            )

class LimitsForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']

    cpu_boundary = common_fields['cpu_boundary']
    cpu_boundary.label = "CPU Boundary (%)"
    cpu_boundary.required = True

    mem_boundary = common_fields['mem_boundary']
    mem_boundary.label = "Memory Boundary (%)"
    mem_boundary.required = True

    disk_read_boundary = common_fields['disk_read_boundary']
    disk_read_boundary.label = "Disk Read Boundary (%)"
    disk_read_boundary.required = True

    disk_write_boundary = common_fields['disk_write_boundary']
    disk_write_boundary.label = "Disk Write Boundary (%)"
    disk_write_boundary.required = True

    energy_boundary = common_fields['energy_boundary']
    energy_boundary.label = "Energy Boundary (%)"
    energy_boundary.required = True

    cpu_boundary_type = common_fields['cpu_boundary_type']
    cpu_boundary_type.required = True

    mem_boundary_type = common_fields['mem_boundary_type']
    mem_boundary_type.required = True

    disk_read_boundary_type = common_fields['disk_read_boundary_type']
    disk_read_boundary_type.required = True

    disk_write_boundary_type = common_fields['disk_write_boundary_type']
    disk_write_boundary_type.required = True

    energy_boundary_type = common_fields['energy_boundary_type']
    energy_boundary_type.required = True

    net_boundary = forms.IntegerField(label="Network Boundary (%)",
            required=True
    )
    net_boundary_type = forms.ChoiceField(label="Network boundary type (percentage of max or current)",
                                           choices=(
                                               ("percentage_of_max", "Percentage of max"),
                                               ("percentage_of_current", "Percentage of current"),
                                           ),
                                           required=False)

    def __init__(self, *args, **kwargs):
        super(LimitsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-limitsForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('cpu_boundary'),
            Field('cpu_boundary_type'),
            Field('mem_boundary'),
            Field('mem_boundary_type'),
            Field('disk_read_boundary'),
            Field('disk_read_boundary_type'),
            Field('disk_write_boundary'),
            Field('disk_write_boundary_type'),
            Field('net_boundary'),
            Field('net_boundary_type'),
            Field('energy_boundary'),
            Field('energy_boundary_type'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )

class RemoveStructureForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "remove"

    structures_removed = forms.MultipleChoiceField(label="Structures Removed",
            choices = (),
            widget=forms.CheckboxSelectMultiple,
            required=False
            )
    def __init__(self, *args, **kwargs):
        super(RemoveStructureForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-removestructureform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('structures_removed'),
            FormActions(
                Submit('save', 'Remove structures', css_class='caja'),
            )    
        )

class AddHostForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add"
    structure_type = common_fields['structure_type']
    structure_type.initial = "host"
    name = common_fields['name']

    cpu_max = common_fields['cpu_max']
    cpu_max.label = "CPU cores"
    mem_max = common_fields['mem_max']
    mem_max.label = "Memory"
    energy_max = common_fields['energy_max']
    energy_max.label = "Energy"

    hdd_disks = forms.IntegerField(label= "HDD disks",
            initial = 0,
            required=True
            )
    hdd_disks_path_list = forms.CharField(label= "HDD disks path list",
            required=False
            )
    ssd_disks = forms.IntegerField(label= "SDD disks",
            initial = 0,
            required=True
            )
    ssd_disks_path_list = forms.CharField(label= "SSD disks path list",
            required=False
            )
    create_lvm = forms.ChoiceField(label="Create LVM",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            initial="False",
            required=True
    )
    lvm_path = forms.CharField(label= "LVM mount path",
            required=False
            )
    number_of_containers = forms.IntegerField(label= "Number of containers",
            initial = 0,
            required=True
            )
    def __init__(self, *args, **kwargs):
        super(AddHostForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-addhostform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'hosts'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('name'),
            Field('cpu_max'),
            Field('mem_max')
        )

        if config['power_budgeting']: self.helper.layout.append(Field('energy_max'))
        if config['disk_capabilities'] and config['disk_scaling']:
            self.helper.layout.append(Field('hdd_disks'))
            self.helper.layout.append(Field('hdd_disks_path_list'))
            self.helper.layout.append(Field('ssd_disks'))
            self.helper.layout.append(Field('ssd_disks_path_list'))
            self.helper.layout.append(Field('create_lvm'))
            self.helper.layout.append(Field('lvm_path'))

        self.helper.layout.append(Field('number_of_containers'))
        self.helper.layout.append(FormActions(Submit('save', 'Add host', css_class='caja')))


class AddDisksToHostsForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add"
    structure_type = common_fields['structure_type']
    structure_type.initial = "disks_to_hosts"

    host_list = forms.MultipleChoiceField(label="Host where to add disks",
            choices = (),
            widget=forms.CheckboxSelectMultiple,
            required=True
            )
    add_to_lv = forms.ChoiceField(label="Add to Logical Volume? (if LV exists)",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            initial="False",
            required=True
            )
    new_disks = forms.CharField(label= "New disks (set device path if adding to LV or mounted directory if adding as individual disks)",
            required=True
            )
    extra_disk = forms.CharField(label= "Extra disk (required if adding to LV)",
            required=False
            )
    threshold = forms.DecimalField(label= "Extension threshold ({0} if unset)".format(DEFAULT_SERVICE_PARAMETERS["lv_extension"]["threshold"]),
            required=False
            )
    polling_frequency = forms.IntegerField(label= "Polling frequency (seconds) ({0} if unset)".format(DEFAULT_SERVICE_PARAMETERS["lv_extension"]["polling_frequency"]),
            required=False
            )
    timeout_events = forms.IntegerField(label= "Timeout events ({0} if unset)".format(DEFAULT_SERVICE_PARAMETERS["lv_extension"]["timeout_events"]),
            required=False
            )

    def __init__(self, *args, **kwargs):
        super(AddDisksToHostsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-adddiskstohostsform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'hosts'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('host_list'),
            Field('add_to_lv'),
            Field('new_disks'),
            Field('extra_disk'),
            Field('threshold'),
            Field('polling_frequency'),
            Field('timeout_events'),
            FormActions(
                Submit('save', 'Add disks to hosts', css_class='caja'),
            )
        )

class AddContainersForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add"
    structure_type = common_fields['structure_type']
    structure_type.initial = "container"
    name = common_fields['name']

    # Resources
    cpu_max = common_fields['cpu_max']
    cpu_min = common_fields['cpu_min']
    cpu_weight = common_fields['cpu_weight']

    mem_max = common_fields['mem_max']
    mem_min = common_fields['mem_min']
    mem_weight = common_fields['mem_weight']

    disk_read_max = common_fields['disk_read_max']
    disk_read_min = common_fields['disk_read_min']
    disk_read_weight = common_fields['disk_read_weight']

    disk_write_max = common_fields['disk_write_max']
    disk_write_min = common_fields['disk_write_min']
    disk_write_weight = common_fields['disk_write_weight']

    energy_max = common_fields['energy_max']
    energy_min = common_fields['energy_min']
    energy_weight = common_fields['energy_weight']

    # Boundaries
    cpu_boundary = common_fields['cpu_boundary']
    mem_boundary = common_fields['mem_boundary']
    disk_read_boundary = common_fields['disk_read_boundary']
    disk_write_boundary = common_fields['disk_write_boundary']
    energy_boundary = common_fields['energy_boundary']

    cpu_boundary_type = common_fields['cpu_boundary_type']
    mem_boundary_type = common_fields['mem_boundary_type']
    disk_read_boundary_type = common_fields['disk_read_boundary_type']
    disk_write_boundary_type = common_fields['disk_write_boundary_type']
    energy_boundary_type = common_fields['energy_boundary_type']

    host_list = forms.CharField(label= "Number of containers to be deployed on each host",
            required=True,
            widget=JSONEditorWidget(width="50%", height="50%", options={'mode':'form', 'name': 'hosts', 'maxVisibleChilds': 10, 'modes': []})
            )

    def __init__(self, *args, **kwargs):
        super(AddContainersForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-addcontainerform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'containers'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('host_list'),
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

        # Submit button
        self.helper.layout.append(FormActions(Submit('save', 'Add container', css_class='caja')))

# Not used ATM
class AddNContainersFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = 'post'
        self.form_id = 'id-addncontainersform'
        self.form_class = 'form-group'
        self.form_method = 'post'
        self.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('host', readonly=True),
            Field('containers_added'),
            FormActions(
                Submit('save-containers', 'Save changes', css_class='caja'),
            )
        )
        self.render_required_fields = True

# Not used ATM
class AddNContainersForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add"
    structure_type = common_fields['structure_type']
    structure_type.initial = "Ncontainers"

    host = forms.CharField(label="Host",
            required=True
            )
    containers_added = forms.IntegerField(label="New Containers",
            initial=0,
            required=True
            )

class AddAppForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add"
    structure_type = common_fields['structure_type']
    structure_type.initial = "apps"
    name = common_fields['name']

    # Resources
    cpu_max = common_fields['cpu_max']
    cpu_min = common_fields['cpu_min']
    cpu_weight = common_fields['cpu_weight']

    mem_max = common_fields['mem_max']
    mem_min = common_fields['mem_min']
    mem_weight = common_fields['mem_weight']

    disk_read_max = common_fields['disk_read_max']
    disk_read_min = common_fields['disk_read_min']
    disk_read_weight = common_fields['disk_read_weight']

    disk_write_max = common_fields['disk_write_max']
    disk_write_min = common_fields['disk_write_min']
    disk_write_weight = common_fields['disk_write_weight']

    energy_max = common_fields['energy_max']
    energy_min = common_fields['energy_min']
    energy_weight = common_fields['energy_weight']

    # Boundaries
    cpu_boundary = common_fields['cpu_boundary']
    mem_boundary = common_fields['mem_boundary']
    disk_read_boundary = common_fields['disk_read_boundary']
    disk_write_boundary = common_fields['disk_write_boundary']
    energy_boundary = common_fields['energy_boundary']

    cpu_boundary_type = common_fields['cpu_boundary_type']
    mem_boundary_type = common_fields['mem_boundary_type']
    disk_read_boundary_type = common_fields['disk_read_boundary_type']
    disk_write_boundary_type = common_fields['disk_write_boundary_type']
    energy_boundary_type = common_fields['energy_boundary_type']

    # App config
    # add_files_dir = common_fields['add_files_dir']
    # files_dir = common_fields['files_dir']
    add_install = common_fields['add_install']
    install_script = common_fields['install_script']
    add_install_files = common_fields['add_install_files']
    install_files = common_fields['install_files']
    add_runtime_files = common_fields['add_runtime_files']
    runtime_files = common_fields['runtime_files']
    add_output_dir = common_fields['add_output_dir']
    output_dir = common_fields['output_dir']
    start_script = common_fields['start_script']
    stop_script = common_fields['stop_script']

    app_dir = forms.CharField(label= "App Directory (name of the directory containing app files)",
                           required=True
                           )

    def __init__(self, *args, **kwargs):
        super(AddAppForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-addappform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'apps'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
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

        # Files for application
        self.helper.layout.append(Field('app_dir'))
        self.helper.layout.append(Field('start_script'))
        self.helper.layout.append(Field('stop_script'))
        # self.helper.layout.append(Field('add_files_dir', css_class='add_files_dir_condition'))
        # self.helper.layout.append(Field('files_dir', css_class='additional_files_dir'))
        self.helper.layout.append(Field('add_install', css_class='add_install_condition'))
        self.helper.layout.append(Field('install_script', css_class='additional_install'))
        self.helper.layout.append(Field('add_install_files', css_class='add_install_files_condition'))
        self.helper.layout.append(Field('install_files', css_class='additional_install_files'))
        self.helper.layout.append(Field('add_runtime_files', css_class='add_runtime_files_condition'))
        self.helper.layout.append(Field('runtime_files', css_class='additional_runtime_files'))
        self.helper.layout.append(Field('add_output_dir', css_class='add_output_dir_condition'))
        self.helper.layout.append(Field('output_dir', css_class='additional_output_dir'))

        # Submit button
        self.helper.layout.append(FormActions(Submit('save', 'Add app', css_class='caja')))


class AddHadoopAppForm(AddAppForm):
    app_type = forms.CharField(label="App type", required=True, initial="hadoop_app")
    app_jar = forms.CharField(label="App JAR", required=True)
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
        # self.helper.layout.append(Field('add_files_dir', css_class='add_files_dir_condition'))
        # self.helper.layout.append(Field('files_dir', css_class='additional_files_dir'))
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
        self.helper.layout.append(Field('app_jar'))

        # Submit button
        self.helper.layout.append(FormActions(Submit('save', 'Add app', css_class='caja')))

class StartAppForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add"
    structure_type = common_fields['structure_type']
    structure_type.initial = "containers_to_app"
    name = common_fields['name']
    name.label = "App"

    number_of_containers = forms.IntegerField(label= "Number of instances",
            required=True
            )
    assignation_policy = forms.ChoiceField(label= "Allocation policy",
            choices = (
                ("Best-effort", "Best effort"),
                ("Fill-up", "Fill up"),
                ("Cyclic", "Cyclic"),
                ),
            required=False
            )
    benevolence = forms.ChoiceField(label= "Scaling benevolence",
            choices = (
                (-1, "Manual"),
                (1, "Lax"),
                (2, "Medium"),
                (3, "Strict"),
                ),
            initial=3,
            required=True
            )

    read_from_global = forms.BooleanField(label="Read files from global HDFS?", required=False)
    global_input = forms.CharField(label="Input file (or directory) to read from global HDFS", required=False)
    local_output = forms.CharField(label="Output directory to write to local HDFS ('{0}' if unset)".format(DEFAULT_HDFS_VALUES["local_output"]), required=False)
    write_to_global = forms.BooleanField(label="Write files to global HDFS?", required=False)
    local_input = forms.CharField(label="Input file (or directory) to read from local HDFS", required=False)
    global_output = forms.CharField(label="Output directory to write to global HDFS ('{0}' if unset)".format(DEFAULT_HDFS_VALUES["global_output"]), required=False)

    def __init__(self, *args, **kwargs):
        super(StartAppForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-startappform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('name', readonly=True),
            Field('number_of_containers'),
            Field('assignation_policy'),
            Field('benevolence'),
        )

        if config['global_hdfs']:
            self.helper.layout.append(Field('read_from_global', type="hidden", css_class='read_from_global_condition'))
            self.helper.layout.append(Field('global_input', css_class='global_input'))
            self.helper.layout.append(Field('local_output', css_class='local_output'))
            self.helper.layout.append(Field('write_to_global', type="hidden", css_class='write_to_global_condition'))
            self.helper.layout.append(Field('local_input', css_class='local_input'))
            self.helper.layout.append(Field('global_output', css_class='global_output'))

        # Submit button
        self.helper.layout.append(FormActions(Submit('save', 'Start App', css_class='caja')))

# Not used ATM
class AddContainersToAppForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add"
    structure_type = common_fields['structure_type']
    structure_type.initial = "containers_to_app"
    name = common_fields['name']
    name.label = "App"

    containers_to_add = forms.MultipleChoiceField(label="Containers to Add",
            choices = (),
            widget=forms.CheckboxSelectMultiple,
            required=False
            )
    fill_with_new_containers = forms.BooleanField(label= "Fill with new containers",
            required=False
            )
    #files_dir = common_fields['files_dir']
    runtime_files = common_fields['runtime_files']
    output_dir = common_fields['output_dir']
    install_script = common_fields['install_script']
    start_script = common_fields['start_script']
    stop_script = common_fields['stop_script']

    def __init__(self, *args, **kwargs):
        super(AddContainersToAppForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-addcontainerstoappform'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('name', readonly=True),
            Field('containers_to_add'),
            Field('fill_with_new_containers'),
            #Field('files_dir',type="hidden", readonly=True),
            Field('runtime_files',type="hidden", readonly=True),
            Field('output_dir',type="hidden", readonly=True),
            Field('install_script',type="hidden", readonly=True),
            Field('start_script',type="hidden", readonly=True),
            Field('stop_script',type="hidden", readonly=True),
            FormActions(
                Submit('save', 'Add Containers to App', css_class='caja'),
            )
        )

class RemoveContainersFromAppForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "remove"

    app = forms.CharField(label= "App",
            required=True
            )
    containers_removed = forms.MultipleChoiceField(label="Structures Removed",
            choices = (),
            widget=forms.CheckboxSelectMultiple,
            required=False
            )

    #files_dir = common_fields['files_dir']
    runtime_files = common_fields['runtime_files']
    output_dir = common_fields['output_dir']
    install_script = common_fields['install_script']
    start_script = common_fields['start_script']
    stop_script = common_fields['stop_script']

    def __init__(self, *args, **kwargs):
        super(RemoveContainersFromAppForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-removecontainersfromapp'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('operation', type="hidden", readonly=True),
            Field('app', type="hidden", readonly=True),
            Field('containers_removed'),
            #Field('files_dir',type="hidden", readonly=True),
            Field('runtime_files',type="hidden", readonly=True),
            Field('output_dir',type="hidden", readonly=True),
            Field('install_script',type="hidden", readonly=True),
            Field('start_script',type="hidden", readonly=True),
            Field('stop_script',type="hidden", readonly=True),
            FormActions(
                Submit('save', 'Remove containers from app', css_class='caja'),
            )
        )

### Services
# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 5, "DEBUG": True, "DOCUMENTS_PERSISTED": ["limits", "structures", "users", "configs"] ,"ACTIVE": True}
class DBSnapshoterForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']
    polling_frequency = common_fields['polling_frequency']

    documents_persisted = forms.MultipleChoiceField(label="Documents Persisted",
            choices = (
                ("structures", "Structures"),
                ("limits", "Limits"),
                ("services", "Services"),
                ("rules", "Rules"),
                ("requests", "Requests"),
                ("events", "Events"),
                ("users", "Users"),
                ("configs", "Configs"),
                ),
            widget=forms.CheckboxSelectMultiple,
            required=False
            )

    def __init__(self, *args, **kwargs):
        super(DBSnapshoterForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-dbsnapshoterForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('debug'),
            Field('documents_persisted'),
            Field('polling_frequency'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )
        )

# CONFIG_DEFAULT_VALUES = {"WINDOW_TIMELAPSE": 10, "WINDOW_DELAY": 10, "EVENT_TIMEOUT": 40, "DEBUG": True, "STRUCTURE_GUARDED": "container", "GUARDABLE_RESOURCES": ["cpu"], "CPU_SHARES_PER_WATT": 5, "ACTIVE": True}
class GuardianForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']
    window_delay = common_fields['window_delay']
    window_timelapse = common_fields['window_timelapse']

    cpu_shares_per_watt = forms.IntegerField(label="Cpu Shares per Watt",
            required=False
            )
    event_timeout = forms.IntegerField(label="Event Timeout (seconds)",
            required=True
            )
    guardable_resources = forms.MultipleChoiceField(label="Guardable Resources",
            choices = (
                ("cpu", "CPU"),
                ("mem", "Memory"),
                ("disk_read", "Disk Read"),
                ("disk_write", "Disk Write"),
                ("net", "Network"),
                ("energy", "Energy"),
                ),
            widget=forms.CheckboxSelectMultiple,
            required=True
            )
    structure_guarded = forms.ChoiceField(label="Structure Guarded",
            choices = (
                ("application", "Application"),
                ("container", "Container"),
                ),
            required=True,
            initial="container"
            )

    energy_model_name = forms.CharField(label= "Energy model name",
            required=False
            )
    use_energy_model = forms.BooleanField(label= "Use energy model?",
            required=False
            )

    def __init__(self, *args, **kwargs):
        super(GuardianForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-guardianForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('cpu_shares_per_watt'),
            Field('debug'),
            Field('event_timeout'),
            Field('guardable_resources'),
            Field('structure_guarded'),
            Field('window_delay'),
            Field('window_timelapse'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )

        if config['power_budgeting']:
            self.helper.layout.append(Field('energy_model_name'))
            self.helper.layout.append(Field('use_energy_model'))

# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 5, "REQUEST_TIMEOUT": 60, "self.debug": True, "CHECK_CORE_MAP": True, "ACTIVE": True}
class ScalerForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']
    polling_frequency = common_fields['polling_frequency']

    check_core_map = forms.ChoiceField(label="Check Core Map",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=False
            )

    request_timeout = forms.IntegerField(label="Request Timeout (seconds)",
            required=True
            )

    def __init__(self, *args, **kwargs):
        super(ScalerForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-scalerForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('check_core_map'),
            Field('debug'),
            Field('polling_frequency'),
            Field('request_timeout'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )

# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 5, "DEBUG": True, "STRUCTURES_PERSISTED": ["application"], "RESOURCES_PERSISTED": ["cpu", "mem"], "ACTIVE": True}
class StructuresSnapshoterForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']
    polling_frequency = common_fields['polling_frequency']

    resources_persisted = forms.MultipleChoiceField(label="Resources Persisted",
            choices = (
                ("cpu", "CPU"),
                ("mem", "Memory"),
                ("disk_read", "Disk Read"),
                ("disk_write", "Disk Write"),
                ("net", "Network"),
                ("energy", "Energy"),
                ),
            widget=forms.CheckboxSelectMultiple,
            required=False
            )

    structures_persisted = forms.MultipleChoiceField(label="Structures Persisted",
            choices = (
                ("application", "Applications"),
                ("user", "Users"),
            ),
            widget=forms.CheckboxSelectMultiple,
            required=False,
            initial=["application"]
            )

    def __init__(self, *args, **kwargs):
        super(StructuresSnapshoterForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-structuressnapshoterForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('debug'),
            Field('polling_frequency'),
            Field('resources_persisted'),
            Field('structures_persisted'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )

# CONFIG_DEFAULT_VALUES = {"DELAY": 120, "DEBUG": True}
class SanityCheckerForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']

    delay = forms.IntegerField(label="Delay (seconds)",
            required=True
            )           

    def __init__(self, *args, **kwargs):
        super(SanityCheckerForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-sanitycheckerForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('debug'),
            Field('delay'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )

# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 10, "WINDOW_TIMELAPSE": 10, "WINDOW_DELAY": 20, "STRUCTURES_REFEEDED": ["application"], "GENERATED_METRICS": ["cpu","mem"], "DEBUG": True}
class RefeederForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']
    window_delay = common_fields['window_delay']
    window_timelapse = common_fields['window_timelapse']

    structures_refeeded = forms.MultipleChoiceField(label="Structures Refeeded",
                                                    choices = (
                                                        ("application", "Applications"),
                                                        ("user", "Users"),
                                                        ),
                                                    widget=forms.CheckboxSelectMultiple,
                                                    required=False,
                                                    initial=["application"]
                                                    )

    generated_metrics = forms.MultipleChoiceField(label="Generated Metrics",
            choices = (
                ("cpu", "CPU"),
                ("mem", "Memory"),
                ("disk_read", "Disk Read"),
                ("disk_write", "Disk Write"),
                #("net", "Network"),
                ("energy", "Energy"),
                ),
            widget=forms.CheckboxSelectMultiple,
            required=False
            )

    def __init__(self, *args, **kwargs):
        super(RefeederForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-refeederForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('debug'),
            Field('structures_refeeded'),
            Field('generated_metrics'),
            Field('window_delay'),
            Field('window_timelapse'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )

# CONFIG_DEFAULT_VALUES = {"WINDOW_TIMELAPSE": 30, "WINDOW_DELAY": 10, "DEBUG": True, "DIFF_PERCENTAGE": 0.40, "STOLEN_PERCENTAGE": 0.40, "RESOURCES_BALANCED": ["cpu"], "STRUCTURES_BALANCED": ["containers"], "CONTAINERS_SCOPE": "application", "BALANCING_POLICY": "rules", "BALANCING_METHOD": "pair_swapping", "ONLY_RUNNING": False}
class ReBalancerForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']
    window_delay = common_fields['window_delay']
    window_timelapse = common_fields['window_timelapse']

    diff_percentage = forms.DecimalField(label="Diff Percentage",
            min_value=0,
            max_value=1,
            required=False
            )
    stolen_percentage = forms.DecimalField(label="Stolen Percentage",
            min_value=0,
            max_value=1,
            required=False
            )

    resources_balanced = forms.MultipleChoiceField(label="Resources to perform balancing",
            choices = (
                ("cpu", "CPU"),
                #("mem", "Memory"),
                ("disk_read", "Disk Read"),
                ("disk_write", "Disk Write"),
                #("net", "Network"),
                ("energy", "Energy")
                ),
            widget=forms.CheckboxSelectMultiple,
            required=False
            )

    structures_balanced = forms.MultipleChoiceField(label="Structures to perform balancing",
            choices = (
                ("container", "Containers"),
                ("application", "Applications"),
                ("user", "Users"),
                ),
            widget=forms.CheckboxSelectMultiple,
            required=False,
            initial=["container"]
            )

    containers_scope = forms.ChoiceField(label="Containers scope to perform container balancing",
                                         choices = (
                                             ("application", "Applications"),
                                             ("host", "Hosts"),
                                         ),
                                         required=False
                                         )

    balancing_policy = forms.ChoiceField(label="Balancing policy to split donors and receivers",
                                         choices = (
                                             ("rules", "Rules"),
                                             ("thresholds", "Thresholds"),
                                         ),
                                         required=False
                                         )

    balancing_method = forms.ChoiceField(label="Balancing method",
                                        choices = (
                                            ("pair_swapping", "Pair swapping"),
                                            ("weights", "Weights"),
                                            ),
                                        required=False
                                        )

    only_running = forms.ChoiceField(label="Only rebalance structures that are running",
                                     choices=(
                                         ("True", "True"),
                                         ("False", "False"),
                                     ),
                                     required=False,
                                     initial=False
                                     )

    def __init__(self, *args, **kwargs):
        super(ReBalancerForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-rebalancerForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('debug'),
            Field('diff_percentage'),
            Field('stolen_percentage'),
            Field('resources_balanced'),
            Field('structures_balanced'),
            Field('containers_scope'),
            Field('balancing_policy'),
            Field('balancing_method'),
            Field('only_running'),
            Field('window_delay'),
            Field('window_timelapse'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )


# CONFIG_DEFAULT_VALUES = {"WINDOW_TIMELAPSE": 10, "WINDOW_DELAY": 10, "GENERATED_METRICS": ["cpu_user", "cpu_kernel", "energy"], "MODELS_TO_TRAIN": ["sgdregressor_General"], "DEBUG": True, "ACTIVE": True}
class WattTrainerForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']
    window_delay = common_fields['window_delay']
    window_timelapse = common_fields['window_timelapse']

#     generated_metrics = forms.MultipleChoiceField(label="Generated Metrics",
#             choices = (
#                 ("cpu", "CPU"),
#                 ("cpu_user", "CPU User"),
#                 ("cpu_kernel", "CPU System"),
#                 ("mem", "Memory"),
#                 ("energy", "Energy"),
#                 ),
#             widget=forms.CheckboxSelectMultiple,
#             required=True
#             )
    models_to_train = forms.MultipleChoiceField(label="Models to train",
            choices = (
                ("sgdregessor_General", "SGDRegressor - General"),
                ("sgdregressor_General", "SGDRegressor - General"),
                ("sgdregressor_Group_P", "SGDRegressor - Group_P"),
                ("sgdregressor_Spread_P", "SGDRegressor - Spread_P"),
                ("sgdregressor_Group_P_and_L", "SGDRegressor - Group_P&L"),
                ("sgdregressor_Spread_P_and_L", "SGDRegressor - Spread_P&L"),
                ("sgdregressor_Group_1P_2_L", "SGDRegressor - Group_1P_2L"),
                ("sgdregressor_Group_PP_LL", "SGDRegressor - Group_PP_LL"),
                ),
            widget=forms.CheckboxSelectMultiple,
            required=True
            )

    def __init__(self, *args, **kwargs):
        super(WattTrainerForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-wattTrainerForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('debug', readonly=True),
            #Field('generated_metrics'),
            Field('models_to_train'),
            Field('window_delay'),
            Field('window_timelapse'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )


# CONFIG_DEFAULT_VALUES = {"GENERATED_METRICS": ["energy"], "DISPATCH_POLICY": "shares-based", "POLLING_FREQUENCY": 10, "DEBUG": True, "ACTIVE": True}
class LimitsDispatcherForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']
    polling_frequency = common_fields['polling_frequency']

    generated_metrics = forms.MultipleChoiceField(label="Generated Metrics",
                                                  choices = (
                                                      ("cpu", "CPU"),
                                                      ("mem", "Memory"),
                                                      ("disk_read", "Disk Read"),
                                                      ("disk_write", "Disk Write"),
                                                      #("net", "Network"),
                                                      ("energy", "Energy"),
                                                  ),
                                                  widget=forms.CheckboxSelectMultiple,
                                                  required=False
                                                  )

    def __init__(self, *args, **kwargs):
        super(LimitsDispatcherForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-limitsDispatcherForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('debug'),
            Field('polling_frequency'),
            Field('generated_metrics'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )
        )

# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 5, "EVENT_TIMEOUT": 20, "WINDOW_TIMELAPSE": 10, "WINDOW_DELAY": 0, "DEBUG": True, "STRUCTURE_GUARDED": "container", "CONTROL_POLICY": "ppe-proportional", "POWER_MODEL": "polyreg_General", "ACTIVE": True}
class EnergyControllerForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']
    debug = common_fields['debug']
    polling_frequency = common_fields['polling_frequency']
    window_delay = forms.IntegerField(label="Window Delay (seconds)", required=True, min_value=0)
    window_timelapse = common_fields['window_timelapse']

    event_timeout = forms.IntegerField(label="Event Timeout (seconds)",
                                       required=True
                                       )

    structure_guarded = forms.ChoiceField(label="Structure Guarded",
                                          choices = (
                                              ("application", "Application"),
                                              ("container", "Container"),
                                          ),
                                          required=True,
                                          initial="container"
                                          )

    control_policy = forms.ChoiceField(label="Control policy",
                                      choices = (
                                          ("ppe-proportional", "PPE-Proportional"),
                                          ("model-boosted", "PPE boosted by power models"),
                                      ),
                                      required=True,
                                      initial="ppe-proportional"
                                      )

    power_model = forms.CharField(label= "Power model name",
                                        required=False
                                        )

    def __init__(self, *args, **kwargs):
        super(EnergyControllerForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-energyControllerForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'services'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('debug'),
            Field('polling_frequency'),
            Field('event_timeout'),
            Field('structure_guarded'),
            Field('window_delay'),
            Field('window_timelapse'),
            Field('control_policy'),
            Field('power_model'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )
        )


### Rules
class RuleForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    name = common_fields['name']

    amount = forms.IntegerField(label="Amount",
            required=False
            )          
    up_events_required = forms.IntegerField(label="Up Events Required",
            min_value=0,
            required=True
            )   
    down_events_required = forms.IntegerField(label="Down Events Required",
            min_value=0,
            required=True
            ) 
    rescale_policy = forms.ChoiceField(label="Rescale Policy",
            choices = (
                ("proportional", "Proportional"),
                ("amount", "Amount"),
                ),
            required=True
            )  

    def __init__(self, *args, **kwargs):
        super(RuleForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-ruleForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'rules' 
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('amount'),
            Field('up_events_required'),
            Field('down_events_required'),
            Field('rescale_policy'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )

### Global HDFS
class AddHdfsFileForm(forms.Form):
    common_fields = deepcopy(DEFAULT_COMMON_FIELDS)
    operation = common_fields['operation']
    operation.initial = "add_file"

    origin_path = forms.CharField(label= "Origin path of file or directory to upload (relative to 'hdfs_data')",
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
    dest_path = forms.CharField(label= "Destination directory (relative to 'hdfs_data')",
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
