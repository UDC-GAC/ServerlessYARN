import os
import json
import urllib

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
        removeContainersFromAppForm.fields['containers_removed'].choices.append(((container['name'],container['host'],disk_path),container['name']))

    app['remove_containers_from_app_form'] = removeContainersFromAppForm
    app['remove_containers_from_app_editable_data'] = editable_data


def getContainerResourcesForApp(number_of_containers, app_resources, app_limits, benevolence, is_hadoop_app):
    container_resources = {}
    container_resources['regular'] = {}
    container_resources['regular']['cpu_max'] = (app_resources['cpu']['max'] - app_resources['cpu']['current']) / number_of_containers

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
                container_resources['bigger'] = container_resources['regular'].copy()
                container_resources['bigger']['cpu_max'] = container_resources['regular']['cpu_max'] + cpu_modulo*(number_of_containers - 1)
                container_resources['regular']['cpu_max'] -= cpu_modulo
                correctly_allocated = True
        # CASE 2: Creating a "smaller" container
        else:
            smaller_resources = container_resources['regular']['cpu_max'] - ((100 - cpu_modulo) * (number_of_containers - 1))
            # Check that the smaller container is not too small
            if smaller_resources >= 10:
                container_resources['smaller'] = container_resources['regular'].copy()
                container_resources['smaller']['cpu_max'] = smaller_resources
                container_resources['regular']['cpu_max'] += (100 - cpu_modulo)
                correctly_allocated = True

    # CPU min and other resources allocation
    if 'bigger' in container_resources or 'smaller' in container_resources:
        irregular = 'bigger' if 'bigger' in container_resources else 'smaller'

        # We will scale resources mantaining the original ratio with cpu_max
        # example: 400/100 max/min shares between 3 containers -> 133.333/33.333 shares each -> modified to 200/50 bigger container and 100/25 regular
        for resource in app_resources:
            for limit in ['max', 'min']:
                key = "{0}_{1}".format(resource, limit)
                if key == "cpu_max":
                    continue
                resource_ratio = app_resources['cpu']['max'] / app_resources[resource][limit]

                for container_type in ['regular', irregular]:
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
                        container_resources[irregular][key] = round(container_resources[irregular][key] + (resource_modulo * (number_of_containers - 1)))
                        container_resources['regular'][key] = int(container_resources['regular'][key])
                else:
                    smaller_resources = container_resources[irregular][key] - ((1 - resource_modulo) * (number_of_containers - 1))
                    if smaller_resources >= 1:
                        container_resources[irregular][key] = round(smaller_resources)
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
    if benevolence == -1:
        # Manual allocation
        for resource in app_resources:
            boundary_key = '{0}_boundary'.format(resource)
            boundary_type_key = '{0}_boundary_type'.format(resource)
            container_resources['regular'][boundary_key] = app_limits[resource]["boundary"]
            container_resources['regular'][boundary_type_key] = app_limits[resource]["boundary_type"]
            if 'bigger' in container_resources or 'smaller' in container_resources:
                irregular = 'bigger' if 'bigger' in container_resources else 'smaller'
                container_resources[irregular][boundary_key] = app_limits[resource]["boundary"]
                container_resources[irregular][boundary_type_key] = app_limits[resource]["boundary_type"]
    else:
        # Automatic allocation
        divider = 2 ** (benevolence + 1)  # benevolence=1 divider=4, benevolence=2 divider=8,...
        for resource in app_resources:
            boundary_key = '{0}_boundary'.format(resource)
            boundary_type_key = '{0}_boundary_type'.format(resource)
            max_key = '{0}_max'.format(resource)
            min_key = '{0}_min'.format(resource)
            container_resources['regular'][boundary_key] = round(
                ((container_resources['regular'][max_key] - container_resources['regular'][min_key]) * 100) /
                (divider * container_resources['regular'][max_key]))
            container_resources['regular'][boundary_type_key] = DEFAULT_LIMIT_VALUES["boundary_type"]

            if 'bigger' in container_resources or 'smaller' in container_resources:
                irregular = 'bigger' if 'bigger' in container_resources else 'smaller'
                container_resources[irregular][boundary_key] = round(
                    ((container_resources[irregular][max_key] - container_resources[irregular][min_key]) * 100) /
                    (divider * container_resources['regular'][max_key]))
                container_resources[irregular][boundary_type_key] = DEFAULT_LIMIT_VALUES["boundary_type"]

    if not correctly_allocated:
        # use original resource allocation
        pass

    # Round cpu max to integer
    container_resources["regular"]["cpu_max"] = round(container_resources["regular"]["cpu_max"])
    if "bigger" in container_resources: container_resources["bigger"]["cpu_max"] = round(container_resources["bigger"]["cpu_max"])
    if "smaller" in container_resources: container_resources["smaller"]["cpu_max"] = round(container_resources["smaller"]["cpu_max"])

    # Weights
    for resource in app_resources:
        weight_key = '{0}_weight'.format(resource)
        container_resources['regular'][weight_key] = app_resources[resource]['weight']
        if 'bigger' in container_resources or 'smaller' in container_resources:
            irregular = 'bigger' if 'bigger' in container_resources else 'smaller'
            container_resources[irregular][weight_key] = app_resources[resource]['weight']

    return container_resources


def getContainerAssignationForApp(assignation_policy, hosts, number_of_containers, container_resources, app_name):

    error = ""
    new_containers = {}
    disk_assignation = {}

    irregular_container_to_allocate = 0
    hadoop_container_to_allocate = 0
    if "smaller" in container_resources or "bigger" in container_resources:
        irregular_container_to_allocate = 1
    if "rm-nn" in container_resources:
        hadoop_container_to_allocate = 1
    containers_to_allocate = number_of_containers - irregular_container_to_allocate - hadoop_container_to_allocate

    assignation = {}
    for host in hosts:
        assignation[host['name']] = {}
        assignation[host['name']]["regular"] = 0
        if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling'] and 'disks' in host['resources']:
            disk_assignation[host['name']] = {}
            for disk_name in host['resources']['disks']:
                disk = host['resources']['disks'][disk_name]
                disk_assignation[host['name']][disk_name] = {}
                disk_assignation[host['name']][disk_name]['new_containers'] = 0
                disk_assignation[host['name']][disk_name]['disk_path'] = disk['path']
                #disk_assignation[host['name']][disk_name]['max_load'] = MAX_DISK_LOAD_DICT[disk['type']] - disk['load']
                disk_assignation[host['name']][disk_name]['free_read'] = disk['free_read']
                disk_assignation[host['name']][disk_name]['free_write'] = disk['free_write']

                consumed_read = disk['max_read'] - disk['free_read']
                consumed_write = disk['max_write'] - disk['free_write']
                disk_assignation[host['name']][disk_name]['free_total'] = max(disk['max_read'],disk['max_write']) - consumed_read - consumed_write


    if assignation_policy == "Fill-up":
        for host in hosts:
            free_cpu = host['resources']['cpu']['free']
            free_mem = host['resources']['mem']['free']
            #free_disk_load = getHostFreeDiskLoad(host)
            if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']: free_read_host, free_write_bw, free_total_bw = getHostFreeDiskBw(host)

            if containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate <= 0:
                break
            # First we try to assign the bigger container if it exists
            if (irregular_container_to_allocate > 0
                    and "bigger" in container_resources
                    and free_cpu >= container_resources["bigger"]['cpu_max']
                    and free_mem >= container_resources["bigger"]['mem_max']
            ):
                if (
                        not settings.PLATFORM_CONFIG['disk_capabilities']
                        or not settings.PLATFORM_CONFIG['disk_scaling']
                        or (free_read_host >= container_resources["bigger"]['disk_read_max']
                            and free_write_host >= container_resources["bigger"]['disk_write_max']
                            and free_total_bw >= max(container_resources["bigger"]['disk_read_max'],container_resources["bigger"]['disk_read_max'])
                        )
                ):
                    assignation[host['name']]["irregular"] = 1
                    irregular_container_to_allocate = 0
                    free_cpu -= container_resources["bigger"]['cpu_max']
                    free_mem -= container_resources["bigger"]['mem_max']
                    if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']:
                        free_read_host -= container_resources["bigger"]['disk_read_max']
                        free_write_host -= container_resources["bigger"]['disk_write_max']
                        free_total_bw -= max(container_resources["bigger"]['disk_read_max'],container_resources["bigger"]['disk_read_max'])
                        for disk in disk_assignation[host['name']]:
                            if (disk_assignation[host['name']][disk]['free_read'] >= container_resources["bigger"]['disk_read_max']
                                    and disk_assignation[host['name']][disk]['free_write'] >= container_resources["bigger"]['disk_write_max']
                                    and disk_assignation[host['name']][disk]['free_total'] >= max(container_resources["bigger"]['disk_read_max'],container_resources["bigger"]['disk_read_max'])
                            ):
                                disk_assignation[host['name']][disk]['free_read'] -= container_resources["bigger"]['disk_read_max']
                                disk_assignation[host['name']][disk]['free_write'] -= container_resources["bigger"]['disk_write_max']
                                disk_assignation[host['name']][disk]['new_containers'] += 1
                                break

            while (containers_to_allocate > 0
                   and free_cpu >= container_resources["regular"]['cpu_max']
                   and free_mem >= container_resources["regular"]['mem_max']
            ):
                if (settings.PLATFORM_CONFIG['disk_capabilities']
                        and settings.PLATFORM_CONFIG['disk_scaling']
                        and (free_read_host < container_resources["regular"]['disk_read_max']
                             or free_write_host < container_resources["regular"]['disk_write_max']
                             or free_total_bw < max(container_resources["regular"]['disk_read_max'],container_resources["regular"]['disk_read_max'])
                        )): break
                assignation[host['name']]["regular"] += 1
                containers_to_allocate -= 1
                free_cpu -= container_resources['regular']['cpu_max']
                free_mem -= container_resources['regular']['mem_max']
                if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']:
                    free_read_host -= container_resources["regular"]['disk_read_max']
                    free_write_host -= container_resources["regular"]['disk_write_max']
                    free_total_bw -= max(container_resources["regular"]['disk_read_max'],container_resources["regular"]['disk_read_max'])
                    for disk in disk_assignation[host['name']]:
                        if (disk_assignation[host['name']][disk]['free_read'] >= container_resources["regular"]['disk_read_max']
                                and disk_assignation[host['name']][disk]['free_write'] >= container_resources["regular"]['disk_write_max']
                                and disk_assignation[host['name']][disk]['free_total'] >= max(container_resources["regular"]['disk_read_max'],container_resources["regular"]['disk_read_max'])
                        ):
                            disk_assignation[host['name']][disk]['free_read'] -= container_resources["regular"]['disk_read_max']
                            disk_assignation[host['name']][disk]['free_write'] -= container_resources["regular"]['disk_write_max']
                            disk_assignation[host['name']][disk]['new_containers'] += 1
                            break

            # We try to assign the smaller container if it exists
            if (irregular_container_to_allocate > 0
                    and "smaller" in container_resources
                    and free_cpu >= container_resources["smaller"]['cpu_max']
                    and free_mem >= container_resources["smaller"]['mem_max']
            ):
                if (not settings.PLATFORM_CONFIG['disk_capabilities']
                        or not settings.PLATFORM_CONFIG['disk_scaling']
                        or (free_read_host >= container_resources["smaller"]['disk_read_max']
                            and free_write_host >= container_resources["smaller"]['disk_write_max']
                            and free_total_bw >= max(container_resources["smaller"]['disk_read_max'],container_resources["smaller"]['disk_read_max'])
                        )
                ):
                    assignation[host['name']]["irregular"] = 1
                    irregular_container_to_allocate = 0
                    free_cpu -= container_resources["smaller"]['cpu_max']
                    free_mem -= container_resources["smaller"]['mem_max']
                    if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']:
                        free_read_host -= container_resources["smaller"]['disk_read_max']
                        free_write_host -= container_resources["smaller"]['disk_write_max']
                        free_total_bw -= max(container_resources["smaller"]['disk_read_max'],container_resources["smaller"]['disk_read_max'])
                        for disk in disk_assignation[host['name']]:
                            if (disk_assignation[host['name']][disk]['free_read'] >= container_resources["smaller"]['disk_read_max']
                                    and disk_assignation[host['name']][disk]['free_write'] >= container_resources["smaller"]['disk_write_max']
                                    and disk_assignation[host['name']][disk]['free_total'] >= max(container_resources["smaller"]['disk_read_max'],container_resources["smaller"]['disk_read_max'])
                            ):
                                disk_assignation[host['name']][disk]['free_read'] -= container_resources["smaller"]['disk_read_max']
                                disk_assignation[host['name']][disk]['free_write'] -= container_resources["smaller"]['disk_write_max']
                                disk_assignation[host['name']][disk]['new_containers'] += 1
                                break

            # Lastly we try to assign the resourcemanager/namenode container if it exists
            if hadoop_container_to_allocate > 0 and "rm-nn" in container_resources and free_cpu >= container_resources["rm-nn"]['cpu_max'] and free_mem >= container_resources["rm-nn"]['mem_max']:
                assignation[host['name']]["rm-nn"] = 1
                hadoop_container_to_allocate = 0
                free_cpu -= container_resources["rm-nn"]['cpu_max']
                free_mem -= container_resources["rm-nn"]['mem_max']

    # Cyclic and Best-effort will now use allocate containers based on min resources instead of max to allow executing multiple containers that try to request all the availables resources from a host
    elif assignation_policy == "Cyclic":
        hosts_without_space = 0
        while containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate > 0 and hosts_without_space < len(hosts):
            for host in hosts:
                if containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate <= 0 or hosts_without_space >= len(hosts):
                    break

                #free_disk_load = getHostFreeDiskLoad(host)
                if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']: free_read_host, free_write_host, free_total_bw = getHostFreeDiskBw(host)

                container_allocated = False
                for container_type in ['bigger', 'regular', 'smaller', 'rm-nn']:
                    if container_type == 'bigger' or container_type == 'smaller':
                        containers_to_check = irregular_container_to_allocate
                    elif container_type == 'rm-nn':
                        containers_to_check = hadoop_container_to_allocate
                    elif container_type == 'regular':
                        containers_to_check = containers_to_allocate

                    if containers_to_check > 0 and container_type in container_resources and host['resources']['cpu']['free'] >= container_resources[container_type]['cpu_min'] and host['resources']['mem']['free'] >= container_resources[container_type]['mem_min']:
                        if not settings.PLATFORM_CONFIG['disk_capabilities'] or not settings.PLATFORM_CONFIG['disk_scaling'] or container_type == "rm-nn" or (
                                free_read_host >= container_resources[container_type]['disk_read_min']
                                and free_write_host >= container_resources[container_type]['disk_write_min']
                                and free_total_bw >= (container_resources[container_type]['disk_read_min'] + container_resources[container_type]['disk_write_min'])
                        ):

                            host['resources']['cpu']['free'] -= container_resources[container_type]['cpu_min']
                            host['resources']['mem']['free'] -= container_resources[container_type]['mem_min']

                            if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling'] and container_type != "rm-nn":
                                host_disk = getFreestDisk(host)
                                if host_disk == None: break

                                if (disk_assignation[host['name']][host_disk]['free_read'] >= container_resources[container_type]['disk_read_min']
                                        and disk_assignation[host['name']][host_disk]['free_write'] >= container_resources[container_type]['disk_write_min']
                                        and disk_assignation[host['name']][host_disk]['free_total'] >= (container_resources[container_type]['disk_read_min'] + container_resources[container_type]['disk_write_min'])
                                ):
                                    disk_assignation[host['name']][host_disk]['free_read'] -= container_resources[container_type]['disk_read_min']
                                    disk_assignation[host['name']][host_disk]['free_write'] -= container_resources[container_type]['disk_write_min']
                                    disk_assignation[host['name']][host_disk]['free_total'] -= (container_resources[container_type]['disk_read_min'] + container_resources[container_type]['disk_write_min'])
                                    disk_assignation[host['name']][host_disk]['new_containers'] += 1
                                    for disk_name in host['resources']['disks']:
                                        disk = host['resources']['disks'][disk_name]
                                        if disk_name == host_disk:
                                            disk['free_read'] -= container_resources[container_type]['disk_read_min']
                                            disk['free_write'] -= container_resources[container_type]['disk_write_min']
                                            break

                            if container_type == 'bigger' or container_type == 'smaller':
                                assignation[host['name']]["irregular"] = 1
                                irregular_container_to_allocate = 0
                            elif container_type == 'rm-nn':
                                assignation[host['name']]["rm-nn"] = 1
                                hadoop_container_to_allocate = 0
                            elif container_type == 'regular':
                                assignation[host['name']]['regular'] += 1
                                containers_to_allocate -= 1

                            container_allocated = True
                            break

                if not container_allocated:
                    hosts_without_space += 1

    elif assignation_policy == "Best-effort":
        while containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate > 0:

            container_allocated = False
            for container_type in ['bigger', 'regular', 'smaller', 'rm-nn']:
                if container_type == 'bigger' or container_type == 'smaller':
                    containers_to_check = irregular_container_to_allocate
                elif container_type == 'rm-nn':
                    containers_to_check = hadoop_container_to_allocate
                elif container_type == 'regular':
                    containers_to_check = containers_to_allocate

                if containers_to_check > 0 and container_type in container_resources:

                    if not settings.PLATFORM_CONFIG['disk_capabilities'] or not settings.PLATFORM_CONFIG['disk_scaling'] or container_type == 'rm-nn':
                        check_disks = False
                    else:
                        check_disks = True

                    freest_host = GetFreestHost(hosts, container_resources[container_type], check_disks)
                    if freest_host == None:
                        break

                    freest_host['resources']['cpu']['free'] -= container_resources[container_type]['cpu_min']
                    freest_host['resources']['mem']['free'] -= container_resources[container_type]['mem_min']

                    if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling'] and container_type != "rm-nn":
                        host_disk = getFreestDisk(freest_host)
                        if host_disk == None: break

                        if (disk_assignation[freest_host['name']][host_disk]['free_read'] >= container_resources[container_type]['disk_read_min']
                                and disk_assignation[freest_host['name']][host_disk]['free_write'] >= container_resources[container_type]['disk_write_min']
                                and disk_assignation[freest_host['name']][host_disk]['free_total'] >= (container_resources[container_type]['disk_read_min'] + container_resources[container_type]['disk_write_min'])
                        ):

                            disk_assignation[freest_host['name']][host_disk]['free_read'] -= container_resources[container_type]['disk_read_min']
                            disk_assignation[freest_host['name']][host_disk]['free_write'] -= container_resources[container_type]['disk_write_min']
                            disk_assignation[freest_host['name']][host_disk]['free_total'] -= (container_resources[container_type]['disk_read_min'] + container_resources[container_type]['disk_write_min'])
                            disk_assignation[freest_host['name']][host_disk]['new_containers'] += 1
                            for disk_name in freest_host['resources']['disks']:
                                disk = host['resources']['disks'][disk_name]
                                if disk_name == host_disk:
                                    disk['free_read'] -= container_resources[container_type]['disk_read_min']
                                    disk['free_write'] -= container_resources[container_type]['disk_write_min']
                                    break

                    if container_type == 'bigger' or container_type == 'smaller':
                        assignation[freest_host['name']]["irregular"] = 1
                        irregular_container_to_allocate = 0
                    elif container_type == 'rm-nn':
                        assignation[freest_host['name']]["rm-nn"] = 1
                        hadoop_container_to_allocate = 0
                    elif container_type == 'regular':
                        assignation[freest_host['name']]['regular'] += 1
                        containers_to_allocate -= 1

                    container_allocated = True
                    break

            if not container_allocated:
                break

    if containers_to_allocate + irregular_container_to_allocate + hadoop_container_to_allocate > 0:
        error = "Could not allocate containers for app {0}: {1}".format(app_name, container_resources)
        return new_containers, disk_assignation, error

    new_containers = {x:y for x,y in assignation.items() if y['regular'] > 0 or "irregular" in y or "rm-nn" in y}

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