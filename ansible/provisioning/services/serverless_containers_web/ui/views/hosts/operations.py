import json
import urllib
import functools
from django.conf import settings

from ui.utils import DEFAULT_SERVICE_PARAMETERS
from ui.background_tasks import register_task, add_host_task, add_disks_to_hosts_task, remove_host_task

from ui.views.core.utils import getStructuresValuesLabels, getLimits, setStructureResourcesForm, setLimitsForm, compareStructureNames, getHostsNames
from ui.views.hosts.utils import setAddHostForm, getContainersFromHost
from ui.views.containers.operations import processRemoveContainers


def getHosts(data):
    hosts = []

    for item in data:
        if item['subtype'] == 'host':
            containers = []
            for structure in data:
                if structure['subtype'] == 'container' and structure['host'] == item['name']:
                    structure['limits'] = getLimits(structure['name'])

                    ## Container Resources Form
                    setStructureResourcesForm(structure,"hosts")

                    ## Container Limits Form
                    setLimitsForm(structure,"hosts")

                    ## Set labels for container values
                    structure['resources_values_labels'] = getStructuresValuesLabels(structure, 'resources')
                    structure['limits_values_labels'] = getStructuresValuesLabels(structure, 'limits')

                    containers.append(structure)

            ## we order this list using name container to keep the order consistent with the 'cpu_cores' dict below
            item['containers'] = sorted(containers, key=functools.cmp_to_key(compareStructureNames))

            # Adjustment to don't let core_usage_mapping be too wide on html display
            if "cpu" in item['resources'] and "core_usage_mapping" in item['resources']['cpu']:

                # Remove removed containers from host core mapping
                core_mapping = {}
                container_names = [d['name'] for d in item['containers']]
                for core, mapping in list(item['resources']['cpu']['core_usage_mapping'].items()):
                    m = {k:v for k,v in mapping.items() if k in container_names or k == "free"}
                    core_mapping[core] = m

                # Core sorting
                core_mapping = {int(k) : v for k, v in core_mapping.items()}
                core_mapping = dict(sorted(core_mapping.items()))

                ## fill usage with 0 when a container doesn't show in a core
                for core,mapping in list(core_mapping.items()):
                    for cont in item['containers']:
                        if (cont['name'] not in mapping):
                            mapping[cont['name']] = 0

                    mapping = dict(sorted(mapping.items(),key=functools.cmp_to_key(compareStructureNames)))

                    ## Move 'free' shares of core always to start of dict
                    free = mapping['free']
                    mapping_list = list(mapping.items())
                    mapping_list.remove(('free',free))
                    mapping_list.insert(0,('free',free))

                    core_mapping[core] = dict(mapping_list)

                item['resources']['cpu_cores'] = core_mapping

                # remove core_usage_mapping from the cpu resources since now that info is in 'cpu_cores'
                item['resources']['cpu'] = {k:v for k,v in item['resources']['cpu'].items() if k != 'core_usage_mapping'}

            ## Host Resources Form
            setStructureResourcesForm(item,"hosts")

            ## Set labels for host values
            item['resources_values_labels'] = getStructuresValuesLabels(item, 'resources')

            hosts.append(item)

    hosts = sorted(hosts,key=functools.cmp_to_key(compareStructureNames))

    return hosts, setAddHostForm(hosts, "hosts")


def processAddHost(request, url, **kwargs):
    error = ""

    new_containers = int(request.POST['number_of_containers'])
    cpu = int(request.POST['cpu_max'])
    mem = int(request.POST['mem_max'])
    energy = int(request.POST['energy_max']) if 'energy_max' in request.POST else None

    # disks
    disk_info = {}
    if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']:
        disk_info['hdd_disks'] = int(request.POST['hdd_disks'])
        disk_info['ssd_disks'] = int(request.POST['ssd_disks'])
        disk_info['create_lvm'] = eval(request.POST['create_lvm'])
        if 'hdd_disks_path_list' in request.POST: disk_info['hdd_disks_path_list'] = request.POST['hdd_disks_path_list'].split(',')
        else: disk_info['hdd_disks_path_list']=[]
        if 'ssd_disks_path_list' in request.POST: disk_info['ssd_disks_path_list'] = request.POST['ssd_disks_path_list'].split(',')
        else: disk_info['ssd_disks_path_list']=[]
        if disk_info['create_lvm']: disk_info['lvm_path'] = request.POST['lvm_path']
        else: disk_info['lvm_path'] = ""

    # provision host and start its containers from playbook
    task = add_host_task.delay(kwargs["structure_name"], cpu, mem, disk_info, energy, new_containers)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id,"add_host_task")

    return error


def processAddDisksToHosts(request, url, **kwargs):

    error = ""

    if 'host_list' in request.POST:
        print(request.POST)
        host_list = request.POST.getlist('host_list', None)
        add_to_lv = eval(request.POST['add_to_lv'])
        new_disks = request.POST['new_disks'].split(',')
        extra_disk = request.POST['extra_disk']

        ## extra params
        if "threshold" in request.POST and request.POST["threshold"] != "": threshold = float(request.POST['threshold'])
        else: threshold = DEFAULT_SERVICE_PARAMETERS["lv_extend"]["threshold"]
        if "polling_frequency" in request.POST and request.POST["polling_frequency"] != "": polling_frequency = int(request.POST['polling_frequency'])
        else: polling_frequency = DEFAULT_SERVICE_PARAMETERS["lv_extend"]["polling_frequency"]
        if "timeout_events" in request.POST and request.POST["timeout_events"] != "": timeout_events = int(request.POST['timeout_events'])
        else: timeout_events = DEFAULT_SERVICE_PARAMETERS["lv_extend"]["timeout_events"]

        if add_to_lv and extra_disk == "":
            error = "Can't add disks to Logical Volume without an extra disk"
            return error

        url = settings.BASE_URL + "/structure/"
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
        hosts_full_info = getHostsNames(data_json)

        measure_host_list = {}
        for host in host_list:

            if not add_to_lv: measure_host = True
            else:
                measure_host = [host_info for host_info in hosts_full_info if host_info["name"] == host][0]["resources"]["disks"]["lvm"]["load"] == 0

            measure_host_list[host] = measure_host

        # add disks from playbook
        task = add_disks_to_hosts_task.delay(host_list, add_to_lv, new_disks, extra_disk, measure_host_list, url, threshold, polling_frequency, timeout_events)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"add_disks_to_hosts_task")

    else:
        error = "No hosts selected"

    return error


def processRemoveHosts(request, url, **kwargs):
    structure_type_url = "host"
    for host in kwargs["selected_structures"]:
        container_list = getContainersFromHost(url, host)
        container_list = ["({0},{1})".format(container, host) for container in container_list]

        # TODO: Remove containers in remove_host_task as done in processRemoveApps to avoid views dependencies
        processRemoveContainers(url, container_list)

        full_url = url + structure_type_url + "/" + host

        task = remove_host_task.delay(full_url, host)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"remove_host_task")
