from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, ButtonHolder, Field, Button
from crispy_forms.bootstrap import FormActions

class RuleForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    amount = forms.IntegerField(label="Amount",
            required=True
            )            

    def __init__(self, *args, **kwargs):
        super(RuleForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()            
        self.helper.form_id = 'id-ruleForm'
        self.helper.form_class = 'form-group'
        self.helper.form_method = 'post'
        self.helper.form_action = 'rules'
        #self.helper.add_input(Submit('submit', 'edit'))  
        self.helper.layout = Layout(
            Field('name', type="hidden", readonly=True),
            Field('amount'),
            #ButtonHolder(
            #    Submit('login', 'Edit')
            #)
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
                #Button('cancel', 'Cancel')
            )    
        )

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
    documents_persisted = forms.JSONField(label="Documents Persisted",
            required=False
            )
    polling_frequency = forms.IntegerField(label="Polling Frequency",
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
                #Button('cancel', 'Cancel')
            )    
        )

# CONFIG_DEFAULT_VALUES = {"WINDOW_TIMELAPSE": 10, "WINDOW_DELAY": 10, "EVENT_TIMEOUT": 40, "DEBUG": True,
#                         "STRUCTURE_GUARDED": "container", "GUARDABLE_RESOURCES": ["cpu"],
#                         "CPU_SHARES_PER_WATT": 5, "ACTIVE": True}
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
    event_timeout = forms.IntegerField(label="Event Timeout",
            required=True
            )
    guardable_resources = forms.JSONField(label="Guardable Resources",
            required=True
            )
    structure_guarded = forms.ChoiceField(label="Structure Guarded",
            choices = (
                ("application", "Application"),
                ("container", "Container"),
                ),
            required=True
            )
    window_delay = forms.IntegerField(label="Window Delay",
            required=True
            )
    window_timelapse = forms.IntegerField(label="Window Timelapse",
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
                #Button('cancel', 'Cancel')
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
    polling_frequency = forms.IntegerField(label="Polling Frequency",
            required=True
            )             
    request_timeout = forms.IntegerField(label="Request Timeout",
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
                #Button('cancel', 'Cancel')
            )    
        )

# CONFIG_DEFAULT_VALUES = {"POLLING_FREQUENCY": 5, "DEBUG": True, "PERSIST_APPS": True, "RESOURCES_PERSISTED": ["cpu", "mem"], "ACTIVE": True}
class StructuresSnapshoterForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            )
    polling_frequency = forms.IntegerField(label="Polling Frequency",
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
    resources_persisted = forms.JSONField(label="Resources Persisted",
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
                #Button('cancel', 'Cancel')
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
    delay = forms.IntegerField(label="Delay",
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
                #Button('cancel', 'Cancel')
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
    generated_metrics = forms.JSONField(label="Generated Metrics",
            required=False
            )  
    polling_frequency = forms.IntegerField(label="Polling Frequency",
            required=False
            )
    window_delay = forms.IntegerField(label="Window Delay",
            required=True
            )
    window_timelapse = forms.IntegerField(label="Window Timelapse",
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
                #Button('cancel', 'Cancel')
            )    
        )