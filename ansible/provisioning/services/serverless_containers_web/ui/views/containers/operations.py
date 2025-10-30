import json
import urllib
import functools
from django.conf import settings

from ui.utils import DEFAULT_LIMIT_VALUES, DEFAULT_RESOURCE_VALUES, SUPPORTED_RESOURCES
from ui.background_tasks import register_task, start_containers_task_v2, remove_containers_task

from ui.views.core.utils import getHostsNames, getLimits, getScalerPollFreq, setStructureResourcesForm, setLimitsForm, getStructuresValuesLabels, compareStructureNames, getFreestDisk
from ui.views.containers.utils import setAddContainersForm


def getContainers(data):
    containers = []
    hosts = getHostsNames(data)
    for item in data:
        if item['subtype'] == 'container':
            item['limits'] = getLimits(item['name'])

            ## Container Resources Form
            setStructureResourcesForm(item,"containers")

            ## Container Limits Form
            setLimitsForm(item,"containers")

            ## Set labels for container values
            item['resources_values_labels'] = getStructuresValuesLabels(item, 'resources')
            item['limits_values_labels'] = getStructuresValuesLabels(item, 'limits')

            containers.append(item)

    containers = sorted(containers, key=functools.cmp_to_key(compareStructureNames))

    return containers, setAddContainersForm(containers, hosts, "containers")


def processAddContainers(request, url, **kwargs):
    error = ""
    container_resources = {}
    host_list = json.loads(kwargs["host_list"].replace("\'","\""))

    for resource in SUPPORTED_RESOURCES:
        if resource + "_max" in request.POST:
            max_res = request.POST[resource + "_max"]
            min_res = request.POST[resource + "_min"]
            if max_res == "" or min_res == "":
                container_resources[resource + "_max"] = "0"
                container_resources[resource + "_min"] = "0"
            else:
                container_resources[resource + "_max"] = max_res
                container_resources[resource + "_min"] = min_res
        if resource + "_weight" in request.POST:
            if request.POST[resource + "_weight"] != "":
                resource_weight = request.POST[resource + "_weight"]
            else:
                resource_weight = DEFAULT_RESOURCE_VALUES["weight"]
            container_resources[resource + "_weight"] = resource_weight
        if resource + "_boundary" in request.POST:
            if request.POST[resource + "_boundary"] != "":
                resource_boundary = request.POST[resource + "_boundary"]
                resource_boundary_type = request.POST[resource + "_boundary_type"]
            else:
                resource_boundary = DEFAULT_LIMIT_VALUES["boundary"]
                resource_boundary_type = DEFAULT_LIMIT_VALUES["boundary_type"]
            container_resources[resource + "_boundary"] = resource_boundary
            container_resources[resource + "_boundary_type"] = resource_boundary_type

    ## Bind specific disk
    bind_disk = "disk_read" in SUPPORTED_RESOURCES and "disk_write" in SUPPORTED_RESOURCES and "disk_read_max" in request.POST and "disk_write_max" in request.POST and request.POST["disk_read_max"] != "" and request.POST["disk_write_max"] != "" and request.POST["disk_read_min"] and request.POST["disk_write_min"]

    # TODO: assign disks to containers in a more efficient way, instead of just choosing the same disk for all containers in the same host
    new_containers = {}
    disks = {}

    hosts_full_info = None
    if bind_disk:
        response = urllib.request.urlopen(settings.BASE_URL + "/structure/")
        data_json = json.loads(response.read())
        hosts_full_info = getHostsNames(data_json)

    for host in host_list:
        new_containers[host] = host_list[host]
        if bind_disk:
            for h in hosts_full_info:
                if h['name'] == host:
                    disks[host] = {}
                    disk = getFreestDisk(h)
                    disks[host]['name'] = disk
                    disks[host]['path'] = h['resources']['disks'][disk]['path']
                    break

    task = start_containers_task_v2.delay(new_containers, container_resources, disks)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"start_containers_task")

    return error


def processRemoveContainers(request, url, **kwargs):
    container_list = []
    for container in kwargs["selected_structures"]:
        cont_host = container.strip("(").strip(")").split(',')
        container = cont_host[0].strip().strip("'")
        host = cont_host[1].strip().strip("'")

        container_list.append({'container_name': container, 'host': host})

    scaler_polling_freq = getScalerPollFreq()

    task = remove_containers_task.delay(url, container_list, scaler_polling_freq)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"remove_containers_task")
