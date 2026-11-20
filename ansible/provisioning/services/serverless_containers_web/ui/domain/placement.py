## Container placement: free resources on hosts and the allocation policies that assign containers to hosts and disks
from django.conf import settings

from serverlessyarn_utils.manage_inventory import AnsibleYamlInventory


def getFreestDisk(host, requested_read_bw, requested_write_bw):

    freest_disk = None

    ## Based on Bandwidth
    current_max_bw = -1

    if 'disks' in host['resources']:
        for disk_name in host['resources']['disks']:

            disk = host['resources']['disks'][disk_name]

            ## Get combined free bandwidth
            consumed_read = disk["max_read"] - disk["free_read"]
            consumed_write = disk["max_write"] - disk["free_write"]
            total_max = max(disk["max_read"],disk["max_write"])
            total_free = total_max - consumed_read - consumed_write

            if (
                disk["free_read"] < requested_read_bw or
                disk["free_write"] < requested_write_bw or
                total_free < requested_read_bw + requested_write_bw
            ):
                continue

            ## TODO: consider if it is better to assign a disk with no containers but low bandwidth or a contended disk with high bw
            if total_free == total_max:
                freest_disk = disk_name
                break

            if current_max_bw == -1 or total_free > current_max_bw:
                current_max_bw = total_free
                freest_disk = disk_name

    return freest_disk


def getFreestHost(hosts, container_resources, check_disks, check_energy, limit_key="min"):

    freest_host = None
    current_min = -1
    for host in hosts:

        # Check cpu and mem space
        if host['resources']['cpu']['free'] < container_resources[f'cpu_{limit_key}'] or host['resources']['mem']['free'] < container_resources[f'mem_{limit_key}']:
            continue

        if check_energy and host['resources']['energy']['free'] < container_resources[f'energy_{limit_key}']:
            continue

        if not check_disks and not check_energy:
            freest_host = host
            break

        if check_energy:
            energy_usage = 1 - host['resources']['energy']['free'] / host['resources']['energy']['max']
            if current_min == -1 or energy_usage < current_min:
                current_min = energy_usage
                freest_host = host
            continue

        # Check that there is at least one suitable disk
        if getFreestDisk(host, container_resources[f'disk_read_{limit_key}'], container_resources[f'disk_write_{limit_key}']) is None:
            continue

        # Get disk usage percentage
        host_disk_free = 0
        host_disk_max = 0

        ## Based on bandwidth
        ## TODO: consider if it is better to assign a disk with no containers but low bandwidth or a contended disk with high bw
        if 'disks' in host['resources']:
            for disk_name in host['resources']['disks']:
                disk = host['resources']['disks'][disk_name]
                consumed_read = disk["max_read"] - disk["free_read"]
                consumed_write = disk["max_write"] - disk["free_write"]
                disk_max = max(disk["max_read"], disk["max_write"])
                disk_free = disk_max - consumed_read - consumed_write

                host_disk_max += disk_max
                host_disk_free += disk_free

        if host_disk_max == 0:
            continue

        host_disk_usage = 1 - (host_disk_free / host_disk_max)

        if host_disk_usage == 0:
            freest_host = host
            break

        if current_min == -1 or host_disk_usage < current_min:
            current_min = host_disk_usage
            freest_host = host

    return freest_host


def getHostFreeDiskBw(host):

    free_read_bw = 0
    free_write_bw = 0
    free_total_bw = 0

    if 'disks' in host['resources']:
        for disk_name in host['resources']['disks']:
            disk = host['resources']['disks'][disk_name]
            free_read_bw += disk['free_read']
            free_write_bw += disk['free_write']

            consumed_read = disk['max_read'] - disk['free_read']
            consumed_write = disk['max_write'] - disk['free_write']
            free_total_bw += max(disk['max_read'], disk['max_write']) - consumed_read - consumed_write

    return free_read_bw, free_write_bw, free_total_bw


def checkAvailableDisk(available_disk, requested_disk, key):
    total = requested_disk[f'disk_read_{key}'] + requested_disk[f'disk_write_{key}']
    return (available_disk["free_read"] >= requested_disk[f'disk_read_{key}'] and
            available_disk["free_write"] >= requested_disk[f'disk_write_{key}'] and
            available_disk["free_total"] >= total)


def checkAvailableResources(host, container, resources, key):
    for res in resources:
        if host['resources'][res]['free'] < container['{0}_{1}'.format(res, key)]:
            return False
    return True


def containersNotAllocated(containers_to_allocate):
    return sum([num for _, num in containers_to_allocate.items()])


def assign_freest_disk(host, container, disk_assignation, limit_key):
    host_disk = getFreestDisk(host, container[f'disk_read_{limit_key}'], container[f'disk_write_{limit_key}'])
    if host_disk is None:
        return False

    # Update disk assignation
    disk_assignation[host['name']][host_disk]['free_read'] -= container[f'disk_read_{limit_key}']
    disk_assignation[host['name']][host_disk]['free_write'] -= container[f'disk_write_{limit_key}']
    disk_assignation[host['name']][host_disk]['free_total'] -= (container[f'disk_read_{limit_key}'] + container[f'disk_write_{limit_key}'])
    disk_assignation[host['name']][host_disk]['new_containers'] += 1

    # Update host for consequent operations
    host['resources']['disks'][host_disk]['free_read'] -= container[f'disk_read_{limit_key}']
    host['resources']['disks'][host_disk]['free_write'] -= container[f'disk_write_{limit_key}']

    return True


def assign_fill_up(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, check_energy, limit_key):
    """
    Completely fills each host with as many containers as possible before moving to the next one. Iterates through the list of hosts sequentially.
    For each host, it allocates containers starting with the largest type ('bigger'), then 'regular', 'smaller', and finally 'master', until the
    host can no longer fit any more containers of that type based on its maximum resource requirements (cpu_max, mem_max). This policy aims to
    consolidate many resources onto a few hosts, leaving other hosts completely free if possible.
    """
    resources_to_check = ["cpu", "mem"] + (["energy"] if check_energy else [])
    for host in hosts:
        if containersNotAllocated(containers_to_allocate) <= 0:
            break

        # We try to assign resources in the following order: bigger container, regular containers, smaller container and resourcemanager/namenode container
        for container_type in ["bigger", "regular", "smaller", "master"]:
            while containers_to_allocate[container_type] > 0:
                available_resources = checkAvailableResources(host, container_resources[container_type], resources_to_check, limit_key)
                if container_type != "master" and check_disks:
                    available_resources = available_resources and any(checkAvailableDisk(
                        disk_assignation[host['name']][disk], container_resources[container_type], limit_key)
                        for disk in disk_assignation[host['name']])
                if not available_resources:
                    break

                assignation[host['name']][container_type] = assignation[host['name']].get(container_type, 0) + 1
                containers_to_allocate[container_type] -= 1
                host['resources']['cpu']['free'] -= container_resources[container_type][f'cpu_{limit_key}']
                host['resources']['mem']['free'] -= container_resources[container_type][f'mem_{limit_key}']
                if container_type != "master" and check_disks:
                    for disk in disk_assignation[host['name']]:
                        if checkAvailableDisk(disk_assignation[host['name']][disk], container_resources[container_type], limit_key):
                            disk_assignation[host['name']][disk]['free_read'] -= container_resources[container_type][f'disk_read_{limit_key}']
                            disk_assignation[host['name']][disk]['free_write'] -= container_resources[container_type][f'disk_write_{limit_key}']
                            disk_assignation[host['name']][disk]['free_total'] -= (container_resources[container_type][f'disk_read_{limit_key}'] + container_resources[container_type][f'disk_write_{limit_key}'])
                            disk_assignation[host['name']][disk]['new_containers'] += 1
                            break


def assign_cyclic(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, check_energy, limit_key):
    """
    Distributes containers one by one across all available hosts in a round-robin fashion. Iterates through the list of available hosts,
    assigning only one container to each host per round, provided the host meets the container's minimum resource requirements (cpu_min, mem_min).
    Hosts that successfully receive a container in a round remain in the pool for the next round. This policy seeks to balance the load among all
    available hosts, preventing a single host from becoming overloaded.
    """
    available_hosts = hosts
    resources_to_check = ["cpu", "mem"] + (["energy"] if check_energy else [])
    while containersNotAllocated(containers_to_allocate) > 0 and len(available_hosts) > 0:
        next_round_hosts = []
        for host in available_hosts:
            # If all containers have been allocated don't try to allocate in the remaining hosts
            if containersNotAllocated(containers_to_allocate) <= 0:
                break

            available_host_disk = {}
            if check_disks:
                available_host_disk["free_read"], available_host_disk["free_write"], available_host_disk["free_total"] = getHostFreeDiskBw(host)

            container_allocated = False
            for container_type in ['bigger', 'regular', 'smaller', 'master']:
                if containers_to_allocate[container_type] > 0:
                    available_resources = checkAvailableResources(host, container_resources[container_type], resources_to_check, limit_key)
                    if container_type != "master" and check_disks:
                        available_resources = available_resources and any(checkAvailableDisk(
                            disk_assignation[host['name']][disk], container_resources[container_type], limit_key)
                            for disk in disk_assignation[host['name']])

                    if available_resources:
                        if container_type != "master" and check_disks:
                            if not assign_freest_disk(host, container_resources[container_type], disk_assignation, limit_key):
                                break
                        host['resources']['cpu']['free'] -= container_resources[container_type][f'cpu_{limit_key}']
                        host['resources']['mem']['free'] -= container_resources[container_type][f'mem_{limit_key}']
                        containers_to_allocate[container_type] -= 1
                        assignation[host['name']][container_type] = assignation[host['name']].get(container_type, 0) + 1
                        container_allocated = True
                        break

            # If host still has available resources, save it for the next round of resources distribution
            if container_allocated:
                next_round_hosts.append(host)

        # Update host list for the next round
        available_hosts = next_round_hosts


def assign_best_effort(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, check_energy, limit_key):
    """
    Prioritizes placing each container on the most suitable host available at that moment. In each step, the algorithm identifies a
    container to be allocated (starting with 'bigger', then 'regular', etc.) and the "freest" host that can fit the container's minimum
    resource requirements (cpu_min, mem_min). The definition of "freest" is determined by the getFreestHost function. Once the best host
    is identified, the container is placed, and its resources are subtracted. This policy aims to keep a balanced load across the hosts
    by always targeting the least-used node for each new allocation.
    """
    while containersNotAllocated(containers_to_allocate) > 0:
        container_allocated = False
        for container_type in ['bigger', 'regular', 'smaller', 'master']:
            if containers_to_allocate[container_type] > 0:
                freest_host = getFreestHost(hosts, container_resources[container_type], container_type != 'master' and check_disks, check_energy, limit_key)
                if freest_host is None:
                    break
                if container_type != 'master' and check_disks:
                    if not assign_freest_disk(freest_host, container_resources[container_type], disk_assignation, limit_key):
                        break
                if check_energy:
                    freest_host['resources']['energy']['free'] -= container_resources[container_type][f'energy_{limit_key}']
                freest_host['resources']['cpu']['free'] -= container_resources[container_type][f'cpu_{limit_key}']
                freest_host['resources']['mem']['free'] -= container_resources[container_type][f'mem_{limit_key}']
                containers_to_allocate[container_type] -= 1
                assignation[freest_host['name']][container_type] = assignation[freest_host['name']].get(container_type, 0) + 1
                container_allocated = True
                break

        if not container_allocated:
            break


def assign_data_locality(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, check_energy, limit_key, locality_scores):
    """
    Places worker containers as close as possible to the data they will read from the global HDFS. Each host has a locality score
    (e.g., bytes of the input data stored on that host), and workers are distributed among the hosts with a positive score
    proportionally to their scores following the highest averages method, i.e., each container is placed on the host that can
    fit it (based on its resource requirements) and maximises 'score / (allocated_workers + 1)'. This way, hosts holding more data
    receive more workers, while workers are still spread across all the hosts holding data. The remaining workers that do not fit
    on hosts holding data, as well as the 'master' container (which does not process data), are allocated following the Best-effort
    policy, prioritising hosts with lower scores to leave room for workers on the hosts holding data.
    """
    resources_to_check = ["cpu", "mem"] + (["energy"] if check_energy else [])
    data_hosts = [host for host in hosts if locality_scores.get(host['name'], 0) > 0]
    allocated_workers = {host['name']: 0 for host in data_hosts}

    for container_type in ['bigger', 'regular', 'smaller']:
        while containers_to_allocate[container_type] > 0:
            candidate_hosts = []
            for host in data_hosts:
                available_resources = checkAvailableResources(host, container_resources[container_type], resources_to_check, limit_key)
                if check_disks:
                    available_resources = available_resources and any(checkAvailableDisk(
                        disk_assignation[host['name']][disk], container_resources[container_type], limit_key)
                        for disk in disk_assignation.get(host['name'], {}))
                if available_resources:
                    candidate_hosts.append(host)

            if not candidate_hosts:
                break

            best_host = max(candidate_hosts, key=lambda h: locality_scores[h['name']] / (allocated_workers[h['name']] + 1))
            if check_disks and not assign_freest_disk(best_host, container_resources[container_type], disk_assignation, limit_key):
                break
            if check_energy:
                best_host['resources']['energy']['free'] -= container_resources[container_type][f'energy_{limit_key}']
            best_host['resources']['cpu']['free'] -= container_resources[container_type][f'cpu_{limit_key}']
            best_host['resources']['mem']['free'] -= container_resources[container_type][f'mem_{limit_key}']
            containers_to_allocate[container_type] -= 1
            assignation[best_host['name']][container_type] = assignation[best_host['name']].get(container_type, 0) + 1
            allocated_workers[best_host['name']] += 1

    # Allocate the remaining containers (if any) and the 'master' container
    sorted_hosts = sorted(hosts, key=lambda h: locality_scores.get(h['name'], 0))
    assign_best_effort(sorted_hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, check_energy, limit_key)


def getContainerAssignationForApp(assignation_policy, allow_oversubscription, hosts, number_of_containers, container_resources, app_name, locality_scores=None):
    error = ""
    new_containers = {}
    disk_assignation = {}
    # Checks "min" instead of "max" to allow executing multiple containers that try to request all the availables resources from a host
    limit_key = "min" if allow_oversubscription else "max"
    check_disks = settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']
    check_energy = settings.PLATFORM_CONFIG['power_budgeting']
    containers_to_allocate = {
        "bigger": 1 if "bigger" in container_resources else 0,
        "smaller": 1 if "smaller" in container_resources else 0,
        "master": 1 if "master" in container_resources else 0
    }
    containers_to_allocate["regular"] = number_of_containers - containers_to_allocate["bigger"] - containers_to_allocate["smaller"] - containers_to_allocate["master"]

    # Initialise assignation
    assignation = {}

    # Reserve server for master containers
    if "master" in container_resources and settings.PLATFORM_CONFIG['server_as_host'] and settings.PLATFORM_CONFIG['reserve_server_for_master']:
        inventory = AnsibleYamlInventory()
        server_name = inventory.get_server_hostname()

        ## Remove server from host list to avoid adding containers to it
        for h in hosts:
            if server_name == h['name']:
                hosts.remove(h)
                break

        assignation[server_name] = {"master": 1}
        containers_to_allocate["master"] = 0


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
                    'free_read': disk['free_read'],
                    'free_write': disk['free_write'],
                    'free_total': max(disk['max_read'],disk['max_write']) - consumed_read - consumed_write
                }

    # Assign resources based on assignation policy
    if assignation_policy == "Fill-up":
        assign_fill_up(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, check_energy, limit_key)
    elif assignation_policy == "Cyclic":
        assign_cyclic(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, check_energy, limit_key)
    elif assignation_policy == "Best-effort":
        assign_best_effort(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, check_energy, limit_key)
    elif assignation_policy == "Data-locality":
        assign_data_locality(hosts, containers_to_allocate, container_resources, assignation, disk_assignation, check_disks, check_energy, limit_key, locality_scores or {})
    else:
        error = f"Assignation policy {assignation_policy} not supported. Try one of [Fill-up, Cyclic, Best-effort, Data-locality]"
        return new_containers, disk_assignation, error

    # Check all containers have been allocated
    if containersNotAllocated(containers_to_allocate) > 0:
        error = "Could not allocate containers for app {0}. Container requested resources: {1}. Hosts free resources: {2}".format(
            app_name,
            {
                c_type: {
                    res: container_resources[c_type][res] for res in container_resources[c_type] if limit_key in res}
                    for c_type in container_resources},
            {
                h['name']: {
                    **{res: h['resources'][res]['free'] for res in ['cpu', 'mem']},
                    **({'energy': h['resources']['energy']['free']} if check_energy else {}),
                    **({
                        'disks': {
                            disk: {
                                free_bw: h['resources']['disks'][disk][free_bw]
                                for free_bw in ['free_read', 'free_write']
                            }
                            for disk in h['resources']['disks']
                        }
                    } if check_disks else {})
                }
                for h in hosts
            },
        )
        return new_containers, disk_assignation, error

    # Format assignation to be used in later phases of the deployment
    for host, host_assignation in assignation.items():
        if host_assignation.get("regular", 0) > 0:
            new_containers.setdefault(host, {})["regular"] = host_assignation["regular"]
        if "smaller" in host_assignation or "bigger" in host_assignation:
            new_containers.setdefault(host, {})["irregular"] = host_assignation.get("bigger", 0) + host_assignation.get("smaller", 0)
        if "master" in host_assignation:
            new_containers.setdefault(host, {})["master"] = host_assignation["master"]

    return new_containers, disk_assignation, error
