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