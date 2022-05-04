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

class DBSnapshoterForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
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
            Field('polling_frequency'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
                #Button('cancel', 'Cancel')
            )    
        )

class GuardianForm(forms.Form):
    name = forms.CharField(label="Name",
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

class ScalerForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    check_core_map = forms.ChoiceField(label="CHECK_CORE_MAP",
            choices = (
                ("True", "On"),
                ("False", "Off"),
            ),
            required=False
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
            Field('polling_frequency'),
            Field('request_timeout'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
                #Button('cancel', 'Cancel')
            )    
        )

class StructuresSnapshoterForm(forms.Form):
    name = forms.CharField(label="Name",
            required=True
            ) 
    polling_frequency = forms.IntegerField(label="Polling Frequency",
            required=True
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
            Field('polling_frequency'),
            FormActions(
                Submit('save', 'Save changes', css_class='caja'),
                #Button('cancel', 'Cancel')
            )    
        )