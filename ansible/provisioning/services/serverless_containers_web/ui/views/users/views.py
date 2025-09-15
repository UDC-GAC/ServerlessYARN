from django.shortcuts import render, redirect

from ui.views.core.operations import processStructures
from ui.views.core.utils import guard_switch, redirect_with_errors
from ui.views.users.operations import getUsers, processAddUser, processRemoveUsers, processSubscribeAppsToUser,processDesubscribeAppsFromUser


# ------------------------------------ Users views ------------------------------------

def users(request):
    operations = {
        "add": processAddUser,
        "remove": processRemoveUsers,
        "get": getUsers,
        "subscribe": processSubscribeAppsToUser,
        "desubscribe": processDesubscribeAppsFromUser
    }

    request, html_render, context, errors = processStructures(request, "users", "users.html", operations)
    if request and html_render and context:
        return render(request, html_render, context)

    return redirect_with_errors("users", errors)


def users_guard_switch(request, app_name):
    # we must be switching an app (users cannot be switched)
    guard_switch(request, app_name)
    return redirect("users")

