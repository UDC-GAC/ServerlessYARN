#!/usr/bin/python

import io
import re
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager

inventory_file = "../../../ansible.inventory"
host_container_separator = "."


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

def add_host(hostname,cpu,mem,new_containers):

    containers = []

    for i in range(0,new_containers,1):
        cont_name = 'cont' + str(i)
        containers.append(hostname + host_container_separator + cont_name)

    write_container_list(containers,hostname,cpu,mem)

def remove_container_from_host(container,hostname):

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostsList = ansible_inventory.groups['nodes'].get_hosts()

    for host in hostsList:

        if (hostname == host.name):

            cpu = host.vars['cpu']
            mem = host.vars['mem']
            containers = host.vars['containers'] 

            if (container in containers): 
                containers.remove(container)
                write_container_list(containers,host.name,cpu,mem)
                
            break

def add_containers_to_hosts(new_containers):

    # example of new_containers argument: {'host0': 2, 'host1': 1}

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostsList = ansible_inventory.groups['nodes'].get_hosts()
    
    for host in hostsList:

        if (host.name in new_containers):
            
            cpu = host.vars['cpu']
            mem = host.vars['mem']
            containers = host.vars['containers']

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
                containers.append(host.name + host_container_separator + cont_name)

            write_container_list(containers,host.name,cpu,mem)


def write_container_list(container_list,host,cpu,mem):
            
    i = 0
    containers_formatted = "\'["

    while (i < len(container_list) - 1):
        containers_formatted += "\"" + container_list[i] + "\","
        i += 1
        
    containers_formatted += "\"" + container_list[i] + "\"]\'"

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

    host_info = host + " cpu=" + str(cpu) + " mem=" + str(mem) + " containers=" + containers_formatted + "\n"

    if (i < len(data)):
        data[i] = host_info
        with open(inventory_file, 'w') as file:
            file.writelines( data )
    else:
        new_line = host_info
        with open(inventory_file, 'a') as file:
            file.writelines( host_info )
