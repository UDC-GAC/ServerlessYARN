from datetime import datetime
from django.shortcuts import render, redirect

from django.conf import settings

from ui.views.core.operations import processStructures
from ui.views.core.utils import guard_switch, redirect_with_errors
from ui.views.apps.operations import getApps, processAddApp, processStartApp, processStopApp, processRemoveApps, processRemoveContainersFromApp

from ui.run_playbooks import drop_host_caches

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
        # example url: http://127.0.0.1:4242/#start=2025/11/28-13:19:45
        #   &m=sum:structure.cpu.current%7Bstructure=Spark_PageRank,structure=Spark_TeraSort,structure=global_hdfs%7D&o=
        #   &m=sum:structure.cpu.usage%7Bstructure=Spark_PageRank,structure=Spark_TeraSort,structure=global_hdfs%7D&o=
        #   &m=sum:structure.disk_read.usage%7Bstructure=Spark_PageRank,structure=Spark_TeraSort,structure=global_hdfs%7D&o=
        #   &m=sum:structure.disk_write.usage%7Bstructure=Spark_PageRank,structure=Spark_TeraSort,structure=global_hdfs%7D&o=
        #   &yrange=%5B0:%5D
        #   &wxh=1600x724
        #   &style=linespoint
        #   &autoreload=5

        app_list = [app['name'] for app in context['data']]
        resource_list = ["cpu", "disk_read", "disk_write"]
        metrics = ["current", "usage"]
        full_metric_string = ""
        if len(app_list) > 0:
            for resource in resource_list:
                for metric in metrics:
                    s = "&m=sum:structure.{0}.{1}%7B".format(resource, metric)
                    for app in app_list[:-1]:
                        s += "structure={0},".format(app)
                    s += "structure={0}%7D&o=".format(app_list[-1])
                    full_metric_string += s

        context['opentsdb'] = "http://{0}:{1}/#start={2}{3}&yrange={4}&wxh={5}&style=linespoint&autoreload={6}".format(
            "127.0.0.1",
            4242,
            datetime.today().strftime('%Y/%m/%d-%H:%M:%S'),
            full_metric_string,
            "%5B0:%5D",
            "1600x724",
            5
        )
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

def drop_caches(request):
    drop_host_caches()
    return redirect("apps")
