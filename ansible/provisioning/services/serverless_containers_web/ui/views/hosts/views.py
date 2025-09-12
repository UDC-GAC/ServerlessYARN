from django.shortcuts import render, redirect

from ui.views.core.operations import processStructures
from ui.views.core.utils import guard_switch, redirect_with_errors
from ui.views.hosts.operations import getHosts, processAddDisksToHosts, processAddHost, processRemoveHosts

# ------------------------------------ Hosts views ------------------------------------

def hosts(request):
    add_operation, rm_operation, get_operation = processAddHost, processRemoveHosts, getHosts
    if request.POST.get('structure_type', "") == "disks_to_hosts":
        add_operation, rm_operation, get_operation = processAddDisksToHosts, processRemoveHosts, getHosts

    request, html_render, context, errors = processStructures(request, "hosts", "hosts.html", add_operation, rm_operation, get_operation)
    if request and html_render and context:
        return render(request, html_render, context)

    return redirect_with_errors("hosts", errors)


def hosts_guard_switch(request, container_name):
    guard_switch(request, container_name)
    return redirect("hosts")