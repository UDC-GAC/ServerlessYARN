from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, ButtonHolder, Field, Button
from crispy_forms.bootstrap import FormActions

### Structures
class HostResourcesFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = 'post'
        self.form_id = 'id-hostresourcesForm'
        self.form_class = 'form-group'
        self.form_method = 'post'
        self.layout = Layout(
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
    name = forms.CharField(label="Name",
            required=True
            )
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
            Field('name', type="hidden", readonly=True),
            Field('structure_type', type="hidden", readonly=True),
            Field('resource', readonly=True),
            Field('guard'),
            Field('max'),
            Field('min'),
            FormActions(
                Submit('save-resources-', 'Save changes', css_class='caja'),
            )
        )
        self.render_required_fields = True

class StructureResourcesForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            )
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

class LimitsForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    cpu_boundary = forms.IntegerField(label="CPU Boundary (CPU percentage)",
            required=False
            )
    mem_boundary = forms.IntegerField(label="Memory Boundary (MB)",
            required=False
            )
    disk_boundary = forms.IntegerField(label="Disk Boundary (MB/s)",
            required=False
            )
    net_boundary = forms.IntegerField(label="Network Boundary (MB/s)",
            required=False
            )
    energy_boundary = forms.IntegerField(label="Energy Boundary (Watts)",
            required=False
            )

    def __init__(self, *args, **kwargs):
        super(LimitsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-limitsForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('cpu_boundary'),
            Field('mem_boundary'),
            Field('disk_boundary'),
            Field('net_boundary'),
            Field('energy_boundary'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )


### Services
# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 5, "DEBUG": True, "DOCUMENTS_PERSISTED": ["limits", "structures", "users", "configs"] ,"ACTIVE": True}
class DBSnapshoterForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    debug = forms.ChoiceField(label="Debug",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=True
            )
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
    polling_frequency = forms.IntegerField(label="Polling Frequency (seconds)",
            required=True
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
    name = forms.CharField(label="Name",
            required=True
            ) 
    cpu_shares_per_watt = forms.IntegerField(label="Cpu Shares per Watt",
            required=False
            )
    debug = forms.ChoiceField(label="Debug",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=True
            )
    event_timeout = forms.IntegerField(label="Event Timeout (seconds)",
            required=True
            )
    guardable_resources = forms.MultipleChoiceField(label="Guardable Resources",
            choices = (
                ("cpu", "CPU"),
                ("mem", "Memory"),
                ("disk", "Disk"),
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
            required=True
            )
    window_delay = forms.IntegerField(label="Window Delay (seconds)",
            required=True
            )
    window_timelapse = forms.IntegerField(label="Window Timelapse (seconds)",
            required=True
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

# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 5, "REQUEST_TIMEOUT": 60, "self.debug": True, "CHECK_CORE_MAP": True, "ACTIVE": True}
class ScalerForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    check_core_map = forms.ChoiceField(label="Check Core Map",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=False
            )
    debug = forms.ChoiceField(label="Debug",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=True
            )
    polling_frequency = forms.IntegerField(label="Polling Frequency (seconds)",
            required=True
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

# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 5, "DEBUG": True, "PERSIST_APPS": True, "RESOURCES_PERSISTED": ["cpu", "mem"], "ACTIVE": True}
class StructuresSnapshoterForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            )   
    debug = forms.ChoiceField(label="Debug",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=True
            )
    persist_apps = forms.ChoiceField(label="Persist Apps",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=False
            )
    polling_frequency = forms.IntegerField(label="Polling Frequency (seconds)",
            required=True
            )   
    resources_persisted = forms.MultipleChoiceField(label="Resources Persisted",
            choices = (
                ("cpu", "CPU"),
                ("mem", "Memory"),
                ("disk", "Disk"),
                ("net", "Network"),
                #("energy", "Energy"),
                ),
            widget=forms.CheckboxSelectMultiple,
            required=False
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
            Field('persist_apps'),
            Field('polling_frequency'),
            Field('resources_persisted'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )

# CONFIG_DEFAULT_VALUES = {"DELAY": 120, "DEBUG": True}
class SanityCheckerForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    debug = forms.ChoiceField(label="Debug",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=True
            )
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

# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 10, "WINDOW_TIMELAPSE": 10, "WINDOW_DELAY": 20, "GENERATED_METRICS": ["cpu","mem"], "DEBUG": True}
class RefeederForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    debug = forms.ChoiceField(label="Debug",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=True
            )
    generated_metrics = forms.MultipleChoiceField(label="Generated Metrics",
            choices = (
                ("cpu", "CPU"),
                ("mem", "Memory"),
                #("disk", "Disk"),
                #("net", "Network"),
                ("energy", "Energy"),
                ),
            widget=forms.CheckboxSelectMultiple,
            required=False
            ) 
    polling_frequency = forms.IntegerField(label="Polling Frequency (seconds)",
            required=False
            )
    window_delay = forms.IntegerField(label="Window Delay (seconds)",
            required=True
            )
    window_timelapse = forms.IntegerField(label="Window Timelapse (seconds)",
            required=True
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
            Field('generated_metrics'),
            Field('polling_frequency'),
            Field('window_delay'),
            Field('window_timelapse'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )

# CONFIG_DEFAULT_VALUES = {"WINDOW_TIMELAPSE": 30, "WINDOW_DELAY": 10, "REBALANCE_USERS": False, "DEBUG": True, "ENERGY_DIFF_PERCENTAGE": 0.40, "ENERGY_STOLEN_PERCENTAGE": 0.40}
class ReBalancerForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    debug = forms.ChoiceField(label="Debug",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=True
            )
    energy_diff_percentage = forms.DecimalField(label="Energy Diff Percentage",
            min_value=0,
            max_value=1,
            required=False
            )
    energy_stolen_percentage = forms.DecimalField(label="Energy Stolen Percentage",
            min_value=0,
            max_value=1,
            required=False
            )
    rebalance_users = forms.ChoiceField(label="Rebalance Users",
            choices = (
                ("True", "True"),
                ("False", "False"),
                ),
            required=False
            )
    window_delay = forms.IntegerField(label="Window Delay (seconds)",
            required=True
            )
    window_timelapse = forms.IntegerField(label="Window Timelapse (seconds)",
            required=True
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
            Field('energy_diff_percentage'),
            Field('energy_stolen_percentage'),
            Field('rebalance_users'),
            Field('window_delay'),
            Field('window_timelapse'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
            )    
        )


### Rules
class RuleForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    amount = forms.IntegerField(label="Amount",
            required=False
            )          
    up_events_required = forms.IntegerField(label="Up Events Required",
            min_value=0,
            required=False
            )   
    down_events_required = forms.IntegerField(label="Down Events Required",
            min_value=0,
            required=False
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