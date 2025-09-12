from django.shortcuts import render, redirect

from ui.views.core.operations import processStructures
from ui.views.core.utils import guard_switch, redirect_with_errors
from ui.views.users.operations import getUsers, processAddUser, processRemoveUsers

# ------------------------------------ Users views ------------------------------------

def users(request):
    add_operation, rm_operation, get_operation = processAddUser, processRemoveUsers, getUsers

    request, html_render, context, errors = processStructures(request, "users", "users.html", add_operation, rm_operation, get_operation)
    if request and html_render and context:
        return render(request, html_render, context)

    return redirect_with_errors("users", errors)


def users_guard_switch(request, app_name):
    # we must be switching an app (users cannot be switched)
    guard_switch(request, app_name)
    return redirect("users")
