import os
import json
import urllib

from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager

from django.conf import settings

from ui.utils import DEFAULT_LIMIT_VALUES
from ui.forms import StartAppForm, RemoveContainersFromAppForm, AddAppForm, AddHadoopAppForm
from ui.views.core.utils import getFreestDisk, GetFreestHost, getHostFreeDiskBw


def getAppInfo(data, app_name):
    app = {}
    for item in data:
        if item['subtype'] == 'application' and item['name'] == app_name:
            return item

    return app


def setStartAppForm(structure, form_action, started_app):
    startAppForm = StartAppForm()
    startAppForm.fields['name'].initial = structure['name']
    startAppForm.helper.form_action = form_action

    structure['start_app_form'] = startAppForm
    structure['started_app'] = started_app

    if settings.PLATFORM_CONFIG['global_hdfs'] and 'framework' in structure and structure['framework'] in ["hadoop", "spark"]:
        structure['start_app_form'].helper['read_from_global'].update_attributes(type="show")
        structure['start_app_form'].helper['write_to_global'].update_attributes(type="show")

def setAddAppForm():
    return {
        'app': AddAppForm(),
        'hadoop_app': AddHadoopAppForm()
    }

def setRemoveContainersFromAppForm(app, containers, form_action):
    removeContainersFromAppForm = RemoveContainersFromAppForm()
    removeContainersFromAppForm.fields['app'].initial = app['name']
    #removeContainersFromAppForm.fields['files_dir'].initial = app['files_dir']
    removeContainersFromAppForm.fields['runtime_files'].initial = app['runtime_files']
    removeContainersFromAppForm.fields['output_dir'].initial = app['output_dir']
    removeContainersFromAppForm.fields['install_script'].initial = app['install_script']
    removeContainersFromAppForm.fields['start_script'].initial = app['start_script']
    removeContainersFromAppForm.fields['stop_script'].initial = app['stop_script']

    removeContainersFromAppForm.helper.form_action = form_action

    editable_data = 0
    for container in containers:
        editable_data += 1
        disk_path = ""
        if 'disk' in container['resources']:
            disk_path = container['resources']['disk']['path']
        removeContainersFromAppForm.fields['selected_structures'].choices.append(((container['name'],container['host'],disk_path),container['name']))

    app['remove_containers_from_app_form'] = removeContainersFromAppForm
    app['remove_containers_from_app_editable_data'] = editable_data


def getContainerResourcesForApp(number_of_containers, app_resources, app_limits, benevolence, is_hadoop_app):
    container_resources = {}
    container_resources['regular'] = {}
    container_resources['regular']['cpu_max'] = (app_resources['cpu']['max'] - app_resources['cpu']['current']) / number_of_containers
    irregular_type = None

    # CPU MAX SHARES ALLOCATION
    # We will try to allocate shares in multiples of 100, then if cpu_max is not a multiple of 100 we will run n-1
    # regular containers whose cpu_max will be adjusted to a multiple of 100 and 1 irregular container that compensates
    # the increase or decrease of the regular containers cpu_max. There are two cases:
    #
    # CASE 1: Creating a "bigger" container:
    # - If `cpu_max` is closer to a lower multiple of 100 (i.e., modulo < 50), we adjust the `cpu_max` of regular
    #   containers to that multiple (regular -= cpu_modulo). Then a bigger container must be created to compensate for
    #   the CPU decrease of the n - 1 regular containers (cpu_modulo * (number_of_containers - 1))
    #
    # CASE 2: Creating a "smaller" container:
    # - If `cpu_max` is closer to the next higher multiple of 100 (i.e., modulo >= 50), we adjust the `cpu_max` of
    #   regular containers up to this multiple (regular += 100 - cpu_modulo). Then a smaller container must be created
    #   to compensate for the extra CPU allocated to each of the n - 1 regular containers ((100 - cpu_modulo) * (number_of_containers - 1))
    # - To avoid undersized containers, this smaller container must have at least 10 CPU shares.
    correctly_allocated = False
    cpu_modulo = container_resources['regular']['cpu_max'] % 100
    # Hadoop apps avoid irregular containers since YARN limits all workers to the smallest container's resources
    if cpu_modulo == 0 or is_hadoop_app:
        # we don't have to do anything
        correctly_allocated = True
    else:
        # CASE 1: Creating a "bigger" container
        if cpu_modulo < 50:
            # Check that it is actually possible for the containers to give shares
            if container_resources['regular']['cpu_max'] > 100:
                irregular_type = 'bigger'
                container_resources['bigger'] = container_resources['regular'].copy()
                container_resources['bigger']['cpu_max'] = container_resources['regular']['cpu_max'] + cpu_modulo*(number_of_containers - 1)
                container_resources['regular']['cpu_max'] -= cpu_modulo
                correctly_allocated = True
        # CASE 2: Creating a "smaller" container
        else:
            smaller_resources = container_resources['regular']['cpu_max'] - ((100 - cpu_modulo) * (number_of_containers - 1))
            # Check that the smaller container is not too small
            if smaller_resources >= 10:
                irregular_type = 'smaller'
                container_resources['smaller'] = container_resources['regular'].copy()
                container_resources['smaller']['cpu_max'] = smaller_resources
                container_resources['regular']['cpu_max'] += (100 - cpu_modulo)
                correctly_allocated = True

    # CPU min and other resources allocation
    if irregular_type:
        # We will scale resources mantaining the original ratio with cpu_max
        # example: 400/100 max/min shares between 3 containers -> 133.333/33.333 shares each -> modified to 200/50 bigger container and 100/25 regular
        for resource in app_resources:
            for limit in ['max', 'min']:
                key = "{0}_{1}".format(resource, limit)
                if key == "cpu_max":
                    continue
                resource_ratio = app_resources['cpu']['max'] / app_resources[resource][limit]

                for container_type in ['regular', irregular_type]:
                    container_resources[container_type][key] = container_resources[container_type]['cpu_max'] / resource_ratio

        # Adjust resource values to integer
        for resource in app_resources:
            for limit in ['max', 'min']:
                key = "{0}_{1}".format(resource, limit)
                if key == "cpu_max":
                    continue

                resource_modulo = container_resources['regular'][key] % 1
                if resource_modulo < 0.5:
                    if container_resources['regular'][key] >= 1:
                        container_resources[irregular_type][key] = round(container_resources[irregular_type][key] + (resource_modulo * (number_of_containers - 1)))
                        container_resources['regular'][key] = int(container_resources['regular'][key])
                else:
                    smaller_resources = container_resources[irregular_type][key] - ((1 - resource_modulo) * (number_of_containers - 1))
                    if smaller_resources >= 1:
                        container_resources[irregular_type][key] = round(smaller_resources)
                        container_resources['regular'][key] = round(container_resources['regular'][key])
    else:
        for resource in app_resources:
            # MIN
            container_resources['regular']['{0}_min'.format(resource)] = int(app_resources[resource]['min'] / number_of_containers)

            # MAX
            if resource == 'cpu':
                continue
            container_resources['regular']['{0}_max'.format(resource)] = int((app_resources[resource]['max'] - app_resources[resource]['current']) / number_of_containers)

    # BOUNDARIES ALLOCATION
    # 2 options:
    #
    # - Manual allocation: Keep the app boundary and boundary_type for all the containers on the app
    #
    # - Automatic allocation: Boundaries for each container are assigned based on resource max and min values
    #   and the benevolence policy as follows: boundary = (max - min) / (2 ** (benevolence + 1))
    #   Example: For 200/100 max/min cpu and a low benevolence value (1 or 'lax' limits):
    #   boundary = (200 - 100) / 4 = 25 -> actual minimum cpu = minimum + 2 * boundary = 100 + 25 * 2 = 150
    #   Then boundaries are converted to a percentage of max, as this is how ServerlessContainers processes them if we
    #   use the default boundary type (percentage_of_max) -> boundary = (boundary / max) * 100
    container_types = {'regular'} if not irregular_type else {'regular', irregular_type}
    if benevolence == -1:
        # Manual allocation
        for resource in app_resources:
            boundary_key = '{0}_boundary'.format(resource)
            boundary_type_key = '{0}_boundary_type'.format(resource)
            for c_type in container_types:
                container_resources[c_type][boundary_key] = app_limits[resource]["boundary"]
                container_resources[c_type][boundary_type_key] = app_limits[resource]["boundary_type"]
    else:
        # Automatic allocation
        divider = 2 ** (benevolence + 1)  # benevolence=1 divider=4, benevolence=2 divider=8,...
        for resource in app_resources:
            boundary_key,boundary_type_key = '{0}_boundary'.format(resource),'{0}_boundary_type'.format(resource)
            max_key, min_key = '{0}_max'.format(resource),'{0}_min'.format(resource)
            for c_type in container_types:
                container_resources[c_type][boundary_key] = round(
                    ((container_resources[c_type][max_key] - container_resources[c_type][min_key]) * 100) /
                    (divider * container_resources[c_type][max_key]))
                container_resources[c_type][boundary_type_key] = DEFAULT_LIMIT_VALUES["boundary_type"]

    if not correctly_allocated:
        # use original resource allocation
        pass

    # Round cpu max to integer
    for c_type in container_types:
        container_resources[c_type]["cpu_max"] = round(container_resources[c_type]["cpu_max"])

    # Weights
    for resource in app_resources:
        weight_key = '{0}_weight'.format(resource)
        for c_type in container_types:
            container_resources[c_type][weight_key] = app_resources[resource]['weight']

    return container_resources


def checkAvailableDisk(available_disk, requested_disk, key):
    total = max(requested_disk['disk_read_max'], requested_disk['disk_write_max']) if key == "max" else requested_disk['disk_read_min'] + requested_disk['disk_write_min']
    return (available_disk["free_read"] >= requested_disk['disk_read_{0}'.format(key)] and
            available_disk["free_write"] >= requested_disk['disk_write_{0}'.format(key)] and
            available_disk["free_total"] >= total)


def checkAvailableResources(host, container, key):
    return host['resources']['cpu']['free'] >= container['cpu_{0}'.format(key)] and host['resources']['mem']['free'] >= container['mem_{0}'.format(key)]


def containersNotAllocated(containers_to_allocate):
    return sum([num for _, num in containers_to_allocate.items()])


def assign_freest_disk(host, container, disk_assignation, limit_key):
    host_disk = getFreestDisk(host)
    if host_disk is None:
        return False

    if checkAvailableDisk(disk_assignation[host['name']][host_disk], container, limit_key):
        disk_assignation[host['name']][host_disk]['free_read'] -= container['disk_read_min']
        disk_assignation[host['name']][host_disk]['free_write'] -= container['disk_write_min']
        disk_assignation[host['name']][host_disk]['free_total'] -= (container['disk_read_min'] + container['disk_write_min'])
        disk_assignation[host['name']][host_disk]['new_containers'] += 1
        for disk_name in host['resources']['disks']:
            disk = host['resources']['disks'][disk_name]
            if disk_name == host_disk:
                disk['free_read'] -= container['disk_read_min']
                disk['free_write'] -= container['disk_write_min']
                break

    return True


def assign_fill_up(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, limit_key):
    """
    Completely fills each host with as many containers as possible before moving to the next one. Iterates through the list of hosts sequentially.
    For each host, it allocates containers starting with the largest type ('bigger'), then 'regular', 'smaller', and finally 'rm-nn', until the
    host can no longer fit any more containers of that type based on its maximum resource requirements (cpu_max, mem_max). This policy aims to
    consolidate many resources onto a few hosts, leaving other hosts completely free if possible.
    """
    for host in hosts:
        if containersNotAllocated(containers_to_allocate) <= 0:
            break

        #free_disk_load = getHostFreeDiskLoad(host)
        available_host_disk = {}
        if check_disks:
            available_host_disk["free_read"], available_host_disk["free_write"], available_host_disk["free_total"] = getHostFreeDiskBw(host)

        # We try to assign resources in the following order: bigger container, regular containers, smaller container and resourcemanager/namenode container
        for container_type in ["bigger", "regular", "smaller", "rm-nn"]:
            while containers_to_allocate[container_type] > 0:
                available_resources = checkAvailableResources(host, container_resources[container_type], limit_key)
                if container_type != "rm-nn" and check_disks:
                    available_resources = available_resources and checkAvailableDisk(available_host_disk, container_resources[container_type], limit_key)
                if not available_resources:
                    break

                assignation[host['name']][container_type] = assignation[host['name']].get(container_type, 0) + 1
                containers_to_allocate[container_type] -= 1
                host['resources']['cpu']['free'] -= container_resources[container_type]['cpu_max']
                host['resources']['mem']['free'] -= container_resources[container_type]['mem_max']
                if container_type != "rm-nn" and check_disks:
                    available_host_disk["free_read"] -= container_resources[container_type]['disk_read_max']
                    available_host_disk["free_write"] -= container_resources["container_type"]['disk_write_max']
                    available_host_disk["free_total"] -= max(container_resources[container_type]['disk_read_max'], container_resources[container_type]['disk_read_max'])
                    for disk in disk_assignation[host['name']]:
                        if checkAvailableDisk(disk_assignation[host['name']][disk], container_resources[container_type], limit_key):
                            disk_assignation[host['name']][disk]['free_read'] -= container_resources[container_type]['disk_read_max']
                            disk_assignation[host['name']][disk]['free_write'] -= container_resources[container_type]['disk_write_max']
                            disk_assignation[host['name']][disk]['new_containers'] += 1
                            break

def assign_cyclic(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, limit_key):
    """
    Distributes containers one by one across all available hosts in a round-robin fashion. Iterates through the list of available hosts,
    assigning only one container to each host per round, provided the host meets the container's minimum resource requirements (cpu_min, mem_min).
    Hosts that successfully receive a container in a round remain in the pool for the next round. This policy seeks to balance the load among all
    available hosts, preventing a single host from becoming overloaded.
    """
    available_hosts = hosts
    while containersNotAllocated(containers_to_allocate) > 0 and len(available_hosts) > 0:
        next_round_hosts = []
        for host in available_hosts:
            # If all containers have been allocated don't try to allocate in the remaining hosts
            if containersNotAllocated(containers_to_allocate) <= 0:
                break

            #free_disk_load = getHostFreeDiskLoad(host)
            available_host_disk = {}
            if check_disks:
                available_host_disk["free_read"], available_host_disk["free_write"], available_host_disk["free_total"] = getHostFreeDiskBw(host)

            container_allocated = False
            for container_type in ['bigger', 'regular', 'smaller', 'rm-nn']:
                if containers_to_allocate[container_type] > 0:
                    available_resources = checkAvailableResources(host, container_resources[container_type], limit_key)
                    if container_type != "rm-nn" and check_disks:
                        available_resources = available_resources and checkAvailableDisk(available_host_disk, container_resources[container_type], limit_key)

                    if available_resources:
                        host['resources']['cpu']['free'] -= container_resources[container_type]['cpu_min']
                        host['resources']['mem']['free'] -= container_resources[container_type]['mem_min']

                        if container_type != "rm-nn" and check_disks:
                            if not assign_freest_disk(host, container_resources[container_type], disk_assignation, limit_key):
                                break

                        containers_to_allocate[container_type] -= 1
                        assignation[host['name']][container_type] = assignation[host['name']].get(container_type, 0) + 1
                        container_allocated = True
                        break

            # If host still has available resources, save it for the next round of resources distribution
            if container_allocated:
                next_round_hosts.append(host)

        # Update host list for the next round
        available_hosts = next_round_hosts


def assign_best_effort(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, limit_key):
    """
    Prioritizes placing each container on the most suitable host available at that moment. In each step, the algorithm identifies a
    container to be allocated (starting with 'bigger', then 'regular', etc.) and the "freest" host that can fit the container's minimum
    resource requirements (cpu_min, mem_min). The definition of "freest" is determined by the GetFreestHost function. Once the best host
    is identified, the container is placed, and its resources are subtracted. This policy aims to keep a balanced load across the hosts
    by always targeting the least-used node for each new allocation.
    """
    while containersNotAllocated(containers_to_allocate) > 0:
        container_allocated = False
        for container_type in ['bigger', 'regular', 'smaller', 'rm-nn']:
            if containers_to_allocate[container_type] > 0:
                freest_host = GetFreestHost(hosts, container_resources[container_type], container_type != 'rm-nn' and check_disks)
                if freest_host is None:
                    break

                freest_host['resources']['cpu']['free'] -= container_resources[container_type]['cpu_min']
                freest_host['resources']['mem']['free'] -= container_resources[container_type]['mem_min']
                if container_type != 'rm-nn' and check_disks:
                    if not assign_freest_disk(freest_host, container_resources[container_type], disk_assignation, limit_key):
                        break

                containers_to_allocate[container_type] -= 1
                assignation[freest_host['name']][container_type] = assignation[freest_host['name']].get(container_type, 0) + 1
                container_allocated = True
                break

        if not container_allocated:
            break

def getContainerAssignationForApp(assignation_policy, allow_oversubscription, hosts, number_of_containers, container_resources, app_name):
    error = ""
    new_containers = {}
    disk_assignation = {}
    # Checks "min" instead of "max" to allow executing multiple containers that try to request all the availables resources from a host
    limit_key = "min" if allow_oversubscription else "max"
    check_disks = settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']
    containers_to_allocate = {
        "bigger": 1 if "bigger" in container_resources else 0,
        "smaller": 1 if "smaller" in container_resources else 0,
        "rm-nn": 1 if "rm-nn" in container_resources else 0
    }
    containers_to_allocate["regular"] = number_of_containers - containers_to_allocate["bigger"] - containers_to_allocate["smaller"] - containers_to_allocate["rm-nn"]

    # Initialise assignation
    assignation = {}

    # Reserve server for master containers
    if "rm-nn" in container_resources and settings.PLATFORM_CONFIG['server_as_host'] and settings.PLATFORM_CONFIG['reserve_server_for_master']:
        loader = DataLoader()
        ansible_inventory = InventoryManager(loader=loader, sources=settings.INVENTORY_FILE)
        server_name = ansible_inventory.groups['platform_management'].get_hosts()[0].vars['ansible_host']

        ## Remove server from host list to avoid adding containers to it
        for h in hosts:
            if server_name == h['name']:
                hosts.remove(h)
                break

        assignation[server_name] = {"rm-nn": 1}
        containers_to_allocate["rm-nn"] = 0


    for host in hosts:
        assignation[host['name']] = {"regular": 0}
        if check_disks and 'disks' in host['resources']:
            disk_assignation[host['name']] = {}
            for disk_name, disk in host['resources']['disks'].items():
                consumed_read = disk['max_read'] - disk['free_read']
                consumed_write = disk['max_write'] - disk['free_write']
                disk_assignation[host['name']][disk_name] = {
                    'new_containers': 0,
                    'disk_path': disk['path'],
                    #'max_load': MAX_DISK_LOAD_DICT[disk['type']] - disk['load']
                    'free_read': disk['free_read'],
                    'free_write': disk['free_write'],
                    'free_total': max(disk['max_read'],disk['max_write']) - consumed_read - consumed_write
                }

    # Assign resources based on assignation policy
    if assignation_policy == "Fill-up":
        assign_fill_up(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, limit_key)
    elif assignation_policy == "Cyclic":
        assign_cyclic(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, limit_key)
    elif assignation_policy == "Best-effort":
        assign_best_effort(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, limit_key)

    # Check all containers have been allocated
    if containersNotAllocated(containers_to_allocate) > 0:
        error = "Could not allocate containers for app {0}: {1}".format(app_name, container_resources)
        return new_containers, disk_assignation, error

    # Format assignation to be used in later phases of the deployment
    for host, host_assignation in assignation.items():
        if host_assignation.get("regular", 0) > 0:
            new_containers.setdefault(host, {})["regular"] = host_assignation["regular"]
        if "smaller" in host_assignation or "bigger" in host_assignation:
            new_containers.setdefault(host, {})["irregular"] = host_assignation.get("bigger", 0) + host_assignation.get("smaller", 0)
        if "rm-nn" in host_assignation:
            new_containers.setdefault(host, {})["rm-nn"] = host_assignation["rm-nn"]

    return new_containers, disk_assignation, error


def checkAppUser(app_name):
    url = settings.BASE_URL + "/user/"
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
    except urllib.error.HTTPError:
        data = {}

    for item in data:
        if app_name in item.get('clusters', []):
            return item['name']

    return None