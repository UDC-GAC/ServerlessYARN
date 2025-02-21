#!/usr/bin/python
import io
import os
import re
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager

scriptDir = os.path.realpath(os.path.dirname(__file__))
inventory_file = scriptDir + "/../../../../ansible.inventory"
host_container_separator = "-"

## Adds
def add_host(hostname,cpu,mem,disk_info,energy,new_containers):

    containers = []

    for i in range(0,new_containers,1):
        cont_name = 'cont' + str(i)
        containers.append(hostname + host_container_separator + cont_name)

    disks = {}
    if disk_info:
        disks = get_disks_dict(disk_info['hdd_disks'],disk_info['hdd_disks_path_list'], disk_info['ssd_disks'], disk_info['ssd_disks_path_list'], disk_info['create_lvm'], disk_info['lvm_path'])

    write_container_list(containers,hostname,cpu,mem,disks,energy)

# Add specific containers to inventory (with their names previously defined)
def add_containers_to_inventory(containers):

    # example of containers argument: [{'container_name': 'host0-cont0', 'host':' 'host0'}, {'container_name': 'host0-cont1', 'host':' 'host0'} ...]

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)
    hostList = ansible_inventory.groups['nodes'].get_hosts()

    for container in containers:

        container_name = container['container_name']
        container_host = container['host']

        matched_host = None
        for host in hostList:
            if host.name == container_host:
                matched_host = host
                break

        if not matched_host: raise Exception("Requested container {0} for host {1} did not match with any of the existing hosts in inventory".format(container_name, container_host))

        cpu = host.vars['cpu']
        mem = host.vars['mem']
        disks = host.vars['disks'] if 'disks' in host.vars else None
        energy = host.vars['energy'] if 'energy' in host.vars else None
        current_containers = host.vars['containers']

        if container_name not in current_containers:
            current_containers.append(container_name)
            write_container_list(current_containers,host.name,cpu,mem,disks,energy)

# Add a number of containers to hosts in inventory (their names will be defined on this function)
def add_containers_to_hosts(new_containers):

    # example of new_containers argument: {'host0': 2, 'host1': 1}

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostList = ansible_inventory.groups['nodes'].get_hosts()
    addedContainers = {}

    for host in hostList:

        if (host.name in new_containers):
            
            cpu = host.vars['cpu']
            mem = host.vars['mem']
            disks = host.vars['disks'] if 'disks' in host.vars else None
            energy = host.vars['energy'] if 'energy' in host.vars else None
            containers = host.vars['containers']
            addedContainers[host.name] = []

            current_containers = len(containers)
            
            last_container_sufix = ""

            if (current_containers > 0):
                last_container_splitted = containers[current_containers - 1].split(host_container_separator)
                last_container_sufix = last_container_splitted[len(last_container_splitted)-1]

            new_container_index = 0
            match = re.match(r"([a-z]+)([0-9]+)", last_container_sufix, re.I)
            if match:
                new_container_index = int(match.groups()[1]) + 1

            for i in range(new_container_index,new_container_index + new_containers[host.name],1):
                cont_name = 'cont' + str(i)
                full_cont_name = host.name + host_container_separator + cont_name
                containers.append(full_cont_name)
                addedContainers[host.name].append(full_cont_name)

            write_container_list(containers,host.name,cpu,mem,disks,energy)

    return addedContainers

def add_disks_to_hosts(hosts_to_add_disks,new_disks):

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostList = ansible_inventory.groups['nodes'].get_hosts()

    added_disks = {}

    pattern = re.compile(r"new_[0-9]+", re.IGNORECASE)

    for host in hostList:
        if host.name in hosts_to_add_disks:

            cpu = host.vars['cpu']
            mem = host.vars['mem']
            disks = host.vars['disks']
            energy = host.vars['energy'] if 'energy' in host.vars else None
            containers = host.vars['containers']
            added_disks[host.name] = {}

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
                    disks[new_disk_name] = {}
                    disks[new_disk_name]['path'] = new_disk

                    added_disks[host.name][new_disk_name] = {}
                    added_disks[host.name][new_disk_name]['path'] = new_disk

                    disk_id += 1

            write_container_list(containers,host.name,cpu,mem,disks,energy)

    return added_disks


## Removes
def remove_host(host_name):

    # read lines
    with open(inventory_file, 'r') as file:
        # read a list of lines into data
        data = file.readlines()

    # write all lines back except the one with the host to delete
    with open(inventory_file, "w") as file:
        for line in data:
            words = line.split(" ")
            if (len(words) > 0):
                if (words[0] != host_name):
                    file.write(line)

def remove_container_from_host(container,hostname):

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostList = ansible_inventory.groups['nodes'].get_hosts()

    for host in hostList:

        if (hostname == host.name):

            cpu = host.vars['cpu']
            mem = host.vars['mem']
            disks = host.vars['disks'] if 'disks' in host.vars else None
            energy = host.vars['energy'] if 'energy' in host.vars else None
            containers = host.vars['containers']

            if (container in containers):
                containers.remove(container)
                write_container_list(containers,host.name,cpu,mem,disks,energy)
            break


## Disks auxiliar
def get_disks_dict(hdd_disks, hdd_disks_path_list, ssd_disks, ssd_disks_path_list, create_lvm, lvm_path):

    disks_dict = {}

    for i in range(ssd_disks):
        disk_name = "ssd_{0}".format(i)
        disk_path = resolve_disk_path(ssd_disks_path_list[i])
        if disk_path != "":
            disks_dict[disk_name] = {}
            disks_dict[disk_name]["path"] = disk_path
        else:
            raise Exception("Disk path can't be empty")

    for i in range(hdd_disks):
        disk_name = "hdd_{0}".format(i)
        disk_path = resolve_disk_path(hdd_disks_path_list[i])
        if disk_path != "":
            disks_dict[disk_name] = {}
            disks_dict[disk_name]["path"] = disk_path
        else:
            raise Exception("Disk path can't be empty")

    if create_lvm:
        lvm_name = "lvm"
        if lvm_path != "":
            disks_dict[lvm_name] = {}
            disks_dict[lvm_name]["path"] = resolve_disk_path(lvm_path)
        else:
            raise Exception("LVM path can't be empty")

    return disks_dict

def update_inventory_disks(hostname, disk, bandwidth_MB):
    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostList = ansible_inventory.groups['nodes'].get_hosts()

    host = None
    for h in hostList:
        if h.name == hostname:
            host = h
            break

    if host == None:
        raise Exception("Host {0} is not on the inventory".format(hostname))

    cpu = host.vars['cpu'] 
    mem = host.vars['mem']
    disks = host.vars['disks']
    energy = host.vars['energy'] if 'energy' in host.vars else None
    containers = host.vars['containers']

    disks[disk]["bw"] = bandwidth_MB

    write_container_list(containers, host.name, cpu, mem, disks, energy)

def resolve_disk_path(disk_path):

    path_parts = disk_path.split("/")
    new_parts = []

    for part in path_parts:
        if '$' in part:
            path_expanded = os.path.expandvars(part)
            if '$' in path_expanded or ' ' in path_expanded:
                # Variable could not be expanded
                return ""
            else:
                new_parts.append(path_expanded)
        else:
            new_parts.append(part)

    return "/".join(new_parts)


## Dump data to inventory
def write_container_list(container_list,host,cpu,mem,disks=None,energy=None):

    # format container list
    i = 0
    containers_formatted = "\'["

    while (i < len(container_list) - 1):
        containers_formatted += "\"" + container_list[i] + "\","
        i += 1

    if len(container_list) > 0:
        containers_formatted += "\"" + container_list[i] + "\"]\'"
    else:
        containers_formatted += "]\'"

    # read lines
    with open(inventory_file, 'r') as file:
        # read a list of lines into data
        data = file.readlines()

    i = 0

    # skip to nodes
    while (i < len(data) and data[i] != "[nodes]\n"):
        i+=1

    i+=1

    # skip to desired node
    while (i < len(data) and host not in data[i]):
        i+=1

    ## Host resources and containers
    host_info = "{0} cpu={1} mem={2}".format(host, str(cpu), str(mem))

    if energy and energy != "None":
        host_info = "{0} energy={1}".format(host_info, str(energy))

    if disks:
        disks_formatted = "\'{0}\'".format(str(disks).replace(" ", "").replace('\'','"'))
        host_info = "{0} disks={1}".format(host_info, disks_formatted)

    host_info = "{0} containers={1}\n".format(host_info, containers_formatted)

    if (i < len(data)):
        data[i] = host_info
        with open(inventory_file, 'w') as file:
            file.writelines( data )
    else:
        new_line = host_info
        with open(inventory_file, 'a') as file:
            file.writelines( host_info )