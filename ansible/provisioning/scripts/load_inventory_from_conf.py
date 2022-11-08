#!/usr/bin/env python
import sys
import io
import yaml
import os
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager

# usage example: load_inventory_from_conf.py /etc/ansible/hosts config/config.yml  -> example outdated

scriptDir = os.path.realpath(os.path.dirname(__file__))
inventory_file = scriptDir + "/../../ansible.inventory"
host_container_separator = "."

def update_server_ip(server_ip):

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostsList = ansible_inventory.groups['server'].get_hosts()

    if (len(hostsList) > 0):
        server = hostsList[0]
        server_info = server.name + " host_ip=" + server_ip + "\n"
    else:
        server_info = "sc-server" + " host_ip=" + server_ip + "\n"

    print(server_info)

    # read lines
    with open(inventory_file, 'r') as file:
        # read a list of lines into data
        data = file.readlines()

    i = 0
    # skip to server
    while (i < len(data) and data[i] != "[server]\n"):
        i+=1
    i+=1

    if (i < len(data)):
        data[i] = server_info
        with open(inventory_file, 'w') as file:
            file.writelines( data )
    else:
        new_line = server_info
        with open(inventory_file, 'a') as file:
            file.writelines( server_info )



def write_inventory_from_conf(number_of_hosts,number_of_containers_per_node,cpu_per_node,mem_per_node):

    structures = {}

    for i in range(0,number_of_hosts,1):
        host_name = 'host' + str(i)
        host_containers = create_container_list(host_name,number_of_containers_per_node)    
        structures[host_name] = {'containers': host_containers, 'cpu': str(cpu_per_node), 'mem': str(mem_per_node)}

    print(structures)

    ## delete all previous host lines
    with open(inventory_file, 'r') as file:
        # read a list of lines into data
        data = file.readlines()

    # write lines until "[nodes]" line (included)
    with open(inventory_file, "w") as file:
        i = 0

        while (i < len(data) and data[i] != "[nodes]\n"):
            file.write(data[i])
            i+= 1
        if (i < len(data)):
            file.write(data[i])

    for host in structures:
        write_container_list(host,structures[host]['cpu'],structures[host]['mem'],structures[host]['containers'])

def update_inventory_hosts_containers(number_of_containers_per_node):

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostsList = ansible_inventory.groups['nodes'].get_hosts()

    structures = {}

    for host in hostsList:
        host_name = host.name
        host_containers = create_container_list(host_name,number_of_containers_per_node)
        structures[host_name] = {'containers': host_containers, 'cpu': host.vars['cpu'], 'mem': host.vars['mem']}

    print(structures)

    for host in structures:
        write_container_list(host,structures[host]['cpu'],structures[host]['mem'],structures[host]['containers'])

def create_container_list(host_name,number_of_containers_per_node):

    host_containers = []

    for i in range(0,number_of_containers_per_node,1):
        cont_name = 'cont' + str(i)
        host_containers.append(host_name + host_container_separator + cont_name)

    return host_containers

def write_container_list(host,cpu,mem,container_list):

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

if __name__ == "__main__":   

    #inventory_file = sys.argv[1]
    #config_file = sys.argv[2]
    config_file = scriptDir + "/../config/config.yml"

    with open(config_file, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    number_of_hosts = config['number_of_client_nodes']
    number_of_containers_per_node = config['number_of_containers_per_node']

    cpu_per_node = config['cpus_per_client_node']
    mem_per_node = config['memory_per_client_node']

    virtual_mode = config['virtual_mode']

    server_ip = config['server_ip']

    update_server_ip(server_ip)

    if (virtual_mode): 
        write_inventory_from_conf(number_of_hosts,number_of_containers_per_node,cpu_per_node,mem_per_node)
    else: 
        update_inventory_hosts_containers(number_of_containers_per_node)