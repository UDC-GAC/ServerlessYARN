from django.shortcuts import render, redirect

from ui.views.core.operations import processStructures
from ui.views.core.utils import guard_switch, redirect_with_errors
from ui.views.containers.operations import getContainers, processAddContainers, processRemoveContainers

# ------------------------------------ Containers views ------------------------------------

def containers(request):
    operations = {
        "add": processAddContainers,
        "remove": processRemoveContainers,
        "get": getContainers
    }

    request, html_render, context, errors = processStructures(request, "containers", "containers.html", operations)
    if request and html_render and context:
        return render(request, html_render, context)

    return redirect_with_errors("containers", errors)


def containers_guard_switch(request, container_name):
    guard_switch(request, container_name)
    return redirect("containers")
