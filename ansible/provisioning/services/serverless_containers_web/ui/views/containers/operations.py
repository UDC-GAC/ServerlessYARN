import json
import urllib
import functools
from django.conf import settings

from ui.utils import DEFAULT_LIMIT_VALUES, DEFAULT_RESOURCE_VALUES, SUPPORTED_RESOURCES
from ui.background_tasks import register_task, start_containers_task_v2, remove_containers_task

from ui.views.core.utils import getHostsNames, getLimits, setStructureResourcesForm, setLimitsForm, getStructuresValuesLabels, compareStructureNames, getFreestDisk, getDbData
from ui.views.containers.utils import setAddContainersForm
from ui.views.apps.utils import checkAvailableResources

def getContainers(data, include_forms=True):
    containers = []
    hosts = getHostsNames(data)
    for item in data:
        if item['subtype'] == 'container':
            item['limits'] = getLimits(item['name'])

            if include_forms:
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
        if f"{resource}_max" in request.POST and f"{resource}_min" in request.POST:
            max_res = request.POST[f"{resource}_max"]
            min_res = request.POST[f"{resource}_min"]
            if max_res == "" or min_res == "":
                container_resources[f"{resource}_max"] = 0
                container_resources[f"{resource}_min"] = 0
            else:
                container_resources[f"{resource}_max"] = max_res
                container_resources[f"{resource}_min"] = min_res
        if f"{resource}_weight" in request.POST:
            if request.POST[f"{resource}_weight"] != "":
                resource_weight = request.POST[f"{resource}_weight"]
            else:
                resource_weight = DEFAULT_RESOURCE_VALUES["weight"]
            container_resources[f"{resource}_weight"] = resource_weight
        if f"{resource}_boundary" in request.POST:
            if request.POST[f"{resource}_boundary"] != "":
                resource_boundary = request.POST[f"{resource}_boundary"]
                resource_boundary_type = request.POST[f"{resource}_boundary_type"]
            else:
                resource_boundary = DEFAULT_LIMIT_VALUES["boundary"]
                resource_boundary_type = DEFAULT_LIMIT_VALUES["boundary_type"]
            container_resources[f"{resource}_boundary"] = resource_boundary
            container_resources[f"{resource}_boundary_type"] = resource_boundary_type

    # Get host data from StateDabase
    response = urllib.request.urlopen(settings.BASE_URL + "/structure/")
    data_json = json.loads(response.read())
    hosts_full_info = getHostsNames(data_json)

    new_containers = {}
    disks = {}

    for host in hosts_full_info:
        hostname = host['name']
        host_requested_containers = host_list.get(hostname, 0)
        host_requested_resources = {res: int(container_resources[res]) * host_requested_containers for res in container_resources if "min" in res and res not in ['disk_read_min', 'disk_write_min']}

        if host_requested_containers > 0 and not checkAvailableResources(
            host,
            host_requested_resources,
            [res[:-4] for res in host_requested_resources], ## :-4 removes the '_min' suffix from resources
            key="min"
        ):
            return f"No resources available for {host_requested_containers} containers in host {hostname}"

        new_containers[hostname] = host_requested_containers

        if "disk_read" in SUPPORTED_RESOURCES and "disk_write" in SUPPORTED_RESOURCES:
            disks[hostname] = {}
            # TODO: assign disks to containers in a more efficient way, instead of just choosing the same disk for all containers in the same host
            disk = getFreestDisk(host, int(container_resources["disk_read_min"]) * host_requested_containers, int(container_resources["disk_write_min"]) * host_requested_containers)
            if not disk:
                return "Error host {0} does not have a disk with enough bandwidth (requested read: {1}, write: {2})".format(
                    hostname,
                    int(container_resources["disk_read_min"]) * host_requested_containers,
                    int(container_resources["disk_write_min"]) * host_requested_containers
                )
            disks[hostname]['name'] = disk
            disks[hostname]['path'] = host['resources']['disks'][disk]['path']

    task = start_containers_task_v2.delay(new_containers, container_resources, disks)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"start_containers_task")

    return error


def processRemoveContainers(request, url, **kwargs):
    container_list = []
    db_containers, _ = getContainers(getDbData(settings.BASE_URL + "/structure/"), include_forms=False)

    for container in kwargs["selected_structures"]:
        cont_host = container.strip("(").strip(")").split(',')
        container_name = cont_host[0].strip().strip("'")
        host_name = cont_host[1].strip().strip("'")

        for db_cont in db_containers:
            if db_cont['name'] == container_name and db_cont['host'] == host_name:
                container_list.append(db_cont)
                break

    task = remove_containers_task.delay(url, container_list)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"remove_containers_task")
