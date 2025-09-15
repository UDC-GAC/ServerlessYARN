from django.shortcuts import render, redirect

from django.conf import settings

from ui.views.core.operations import processStructures
from ui.views.core.utils import guard_switch, redirect_with_errors
from ui.views.apps.operations import getApps, processAddApp, processStartApp, processStopApp, processRemoveApps, processRemoveContainersFromApp

# ------------------------------------ Apps views ------------------------------------

def apps(request):
    operations = {
        "add": processAddApp,
        "remove": processRemoveApps,
        "desubscribe": processRemoveContainersFromApp,
        "get": getApps,
        "start": processStartApp
    }

    request, html_render, context, errors = processStructures(request, "apps","apps.html", operations)
    if request and html_render and context:
        return render(request, html_render, context)

    return redirect_with_errors("apps", errors)


def apps_guard_switch(request, structure_name):
    # we may be switching a container or an app
    guard_switch(request, structure_name)
    return redirect("apps")


def apps_stop_switch(request, structure_name):
    url = settings.BASE_URL + "/structure/"
    errors = processStopApp(url, structure_name)
    # TODO: Redirect with errors??
    return redirect("apps")