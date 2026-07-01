#!/usr/bin/python
import os
import re
import sys

scriptDir = os.path.realpath(os.path.dirname(__file__))

sys.path.append(scriptDir + "/../../../scripts/utils")
from manage_inventory import AnsibleYamlInventory, get_disks_dict, create_container_list, HOST_CONTAINER_SEPARATOR

## Adds
def add_host(hostname,cpu,mem,disk_info,energy,new_containers):

    containers = create_container_list(hostname, new_containers)

    disks = {}
    if disk_info:
        disks = get_disks_dict(
            disk_info['hdd_disks'],
            disk_info['hdd_disks_path_list'],
            disk_info['ssd_disks'],
            disk_info['ssd_disks_path_list'],
            disk_info['create_lvm'],
            disk_info['lvm_path']
        )

    inventory = AnsibleYamlInventory()
    inventory.add_node(hostname=hostname, resources={'cpu': cpu, 'mem': mem, 'disks': disks, 'energy': energy}, containers=containers)
    inventory.save()

# Add specific containers to inventory (with their names previously defined)
def add_containers_to_inventory(containers):

    # example of containers argument: [{'container_name': 'host0-cont0', 'host':' 'host0'}, {'container_name': 'host0-cont1', 'host':' 'host0'} ...]
    inventory = AnsibleYamlInventory()
    for container in containers:
        inventory.add_container(hostname=container['host'], container=container['container_name'])
    inventory.save()

# Add a number of containers to hosts in inventory (their names will be defined on this function)
def add_containers_to_hosts(new_containers):

    # example of new_containers argument: {'host0': 2, 'host1': 1}
    inventory = AnsibleYamlInventory()
    added_containers = {}

    for host in new_containers:
        containers = inventory.get_containers(host)
        current_containers = len(containers)

        ## Create container names based on last defined name
        ### e.g., if last container is named 'host0-cont2', newer ones should be named 'host0-cont3', 'host0-cont4', and so on
        last_container_sufix = ""

        if (current_containers > 0):
            last_container_splitted = containers[current_containers - 1].split(HOST_CONTAINER_SEPARATOR)
            last_container_sufix = last_container_splitted[len(last_container_splitted)-1]

        new_container_index = 0
        match = re.match(r"([a-z]+)([0-9]+)", last_container_sufix, re.I)
        if match:
            new_container_index = int(match.groups()[1]) + 1

        added_containers[host] = create_container_list(host_name=host, number_of_containers=new_containers[host], first_index=new_container_index)

        inventory.add_containers(hostname=host, containers=added_containers[host])

    inventory.save()
    return added_containers

def add_disks_to_hosts(hosts_to_add_disks, new_disks):

    inventory = AnsibleYamlInventory()
    added_disks = {}
    pattern = re.compile(r"new_[0-9]+", re.IGNORECASE)

    for host in hosts_to_add_disks:
        added_disks[host] = {}
        disks = inventory.get_disks(host)

        ## Create disk names based on last defined name, following the pattern 'new_<id>'
        disk_id = 0
        existing_disks = []
        for d in disks:
            existing_disks.append(disks[d]['path'])
            if pattern.match(d):
                i = int(d.split("_")[1])
                if i >= disk_id: disk_id = i + 1

        for new_disk in new_disks:
            if new_disk not in existing_disks:
                ## It is probably better not to bother differentiating between HDD and SSD disks since measured bandwidth will be used to differentiate them
                new_disk_name = "new_{0}".format(disk_id)
                added_disks[host][new_disk_name] = {}
                added_disks[host][new_disk_name]['path'] = new_disk
                disk_id += 1

        inventory.add_disks(hostname=host, disks=added_disks[host])

    inventory.save()
    return added_disks


## Removes
def remove_host(host_name):

    inventory = AnsibleYamlInventory()
    inventory.remove_node(host_name)
    inventory.save()

def remove_container_from_host(container,hostname):

    inventory = AnsibleYamlInventory()
    inventory.remove_container(hostname=hostname, container=container)
    inventory.save()

def update_inventory_disk(hostname, disk, read_bandwidth_MB, write_bandwidth_MB):

    inventory = AnsibleYamlInventory()
    inventory.update_disk(hostname=hostname, disk=disk, new_disk_info={"read_bw": read_bandwidth_MB, "write_bw": write_bandwidth_MB})
    inventory.save()
