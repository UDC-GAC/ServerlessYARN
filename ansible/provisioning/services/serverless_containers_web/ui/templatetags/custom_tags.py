from django import template

register = template.Library()

@register.simple_tag
def get_view_list():
    return [
        ('index', 'Home'), 
        ('containers', 'Containers'), 
        ('hosts', 'Hosts'), 
        ('apps', 'Apps'), 
        ('services', 'Services'), 
        ('rules', 'Rules')
    ]

@register.filter
def is_not_none(value):
    return value is not None


@register.filter(name='dict_key')
def dict_key(d, k):
    return d.get(k, "")