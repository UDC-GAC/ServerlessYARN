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

def add_host(hostname,cpu,mem,disk_info,new_containers):

    containers = []

    for i in range(0,new_containers,1):
        cont_name = 'cont' + str(i)
        containers.append(hostname + host_container_separator + cont_name)

    disks = get_disks_dict(disk_info['hdd_disks'],disk_info['hdd_disks_path_list'], disk_info['ssd_disks'], disk_info['ssd_disks_path_list'], disk_info['create_lvm'], disk_info['lvm_path'])

    write_container_list(containers,hostname,cpu,mem,disks)

def remove_container_from_host(container,hostname):

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostsList = ansible_inventory.groups['nodes'].get_hosts()

    for host in hostsList:

        if (hostname == host.name):

            cpu = host.vars['cpu']
            mem = host.vars['mem']
            disks = host.vars['disks']
            containers = host.vars['containers'] 

            if (container in containers): 
                containers.remove(container)
                write_container_list(containers,host.name,cpu,mem,disks)
                
            break

def add_containers_to_hosts(new_containers):

    # example of new_containers argument: {'host0': 2, 'host1': 1}

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostsList = ansible_inventory.groups['nodes'].get_hosts()
    addedContainers = {}

    for host in hostsList:

        if (host.name in new_containers):
            
            cpu = host.vars['cpu']
            mem = host.vars['mem']
            disks = host.vars['disks']
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

            write_container_list(containers,host.name,cpu,mem,disks)

    return addedContainers

def write_container_list(container_list,host,cpu,mem,disks):

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

    # format disk dict
    disks_formatted = "\'{0}\'".format(str(disks).replace(" ", "").replace('\'','"'))

    i = 0

    # skip to nodes
    while (i < len(data) and data[i] != "[nodes]\n"):
        i+=1

    i+=1

    # skip to desired node
    while (i < len(data) and host not in data[i]):
        i+=1

    host_info = "{0} cpu={1} mem={2} disks={3} containers={4}\n".format(host, str(cpu), str(mem), disks_formatted, containers_formatted)

    if (i < len(data)):
        data[i] = host_info
        with open(inventory_file, 'w') as file:
            file.writelines( data )
    else:
        new_line = host_info
        with open(inventory_file, 'a') as file:
            file.writelines( host_info )

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

    hostsList = ansible_inventory.groups['nodes'].get_hosts()

    host = None
    for h in hostsList:
        if h.name == hostname:
            host = h
            break

    if host == None:
        raise Exception("Host {0} is not on the inventory".format(hostname))

    cpu = host.vars['cpu']
    mem = host.vars['mem']
    disks = host.vars['disks']
    containers = host.vars['containers']

    disks[disk]["bw"] = bandwidth_MB

    write_container_list(containers,host.name,cpu,mem,disks)


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