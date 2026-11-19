import re
import json
import functools
import urllib


def compareStructureNames(structure1, structure2):
    # When using a dict to store container info
    if isinstance(structure1, dict):
        cname1 = structure1['name']
        cname2 = structure2['name']
    # When using a tuple to store container info (host core mapping case))
    elif isinstance(structure1, tuple):
        cname1 = structure1[0]
        cname2 = structure2[0]
    # When using containers as strings
    else:
        cname1 = structure1
        cname2 = structure2

    id1 = re.sub('.*?([0-9]*)$',r'\1',cname1)
    id2 = re.sub('.*?([0-9]*)$',r'\1',cname2)

    if id1 != "" and id2 != "":
        basename1 = cname1[:-len(id1)]
        basename2 = cname2[:-len(id2)]
    else:
        basename1 = cname1
        basename2 = cname2

    if basename1 < basename2:
        return -1
    elif basename1 > basename2:
        return 1
    else:
        if id1 != "" and id2 != "":
            if int(id1) < int(id2):
                return -1
            elif int(id1) > int(id2):
                return 1
            else:
                return 0
        else:
            return 0


def getDbData(url):

    try:
        response = urllib.request.urlopen(url)
        data_json = json.loads(response.read())
    except urllib.error.HTTPError:
        data_json = {}

    return data_json


def getHostsNames(data):
    hosts = []
    for item in data:
        if item['subtype'] == 'host':
            hosts.append(item)

    hosts = sorted(hosts, key=functools.cmp_to_key(compareStructureNames))
    return hosts


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


def getDataAndFilterByApp(url, app_name):
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
    except urllib.error.HTTPError:
        data = {}

    for item in data:
        if item['subtype'] == 'application' and item['name'] == app_name:
            return data, item
    return data, None
