#!/usr/bin/env python
import sys
import io
import os
import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from copy import deepcopy

scriptDir = os.path.realpath(os.path.dirname(__file__))
inventory_file = scriptDir + "/../../ansible.inventory"
host_container_separator = "-"

sys.path.append(scriptDir + "/../services/serverless_containers_web/ui")
from update_inventory_file import write_container_list, get_disks_dict, resolve_disk_path

def update_server_ip(server_ip):

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostList = ansible_inventory.groups['platform_management'].get_hosts()

    if (len(hostList) > 0):
        server = hostList[0]
        server_info = "{0} host_ip={1} ansible_host={2}\n".format(server.name, server_ip, server.vars['ansible_host'])
    else:
        server_info = "{0} host_ip={1} ansible_host={2}\n".format("platform_server", server_ip, "server")

    print(server_info)

    # read lines
    with open(inventory_file, 'r') as file:
        # read a list of lines into data
        data = file.readlines()

    i = 0
    # skip to server
    while (i < len(data) and data[i] != "[platform_management]\n"):
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


def write_inventory_from_conf(config,disks_dict):

    number_of_hosts = config['number_of_hosts']
    server_as_host = config['server_as_host']
    number_of_containers_per_node = config['number_of_containers_per_node']

    cpu_per_node = config['cpus_per_host']
    mem_per_node = config['memory_per_host']
    energy_per_node = config['energy_per_host'] if config['power_budgeting'] else None

    structures = {}

    if server_as_host:
        host_name = 'server'
        host_containers = create_container_list(host_name,number_of_containers_per_node)
        server_disk_dict = disks_dict

        ## Add specific disk for HDFS namenode when also acting as frontend
        if config['global_hdfs']:
            disk_name = config['global_hdfs_disk_name']
            server_disk_dict = deepcopy(disks_dict)
            server_disk_dict[disk_name] = {}
            server_disk_dict[disk_name]['path'] = resolve_disk_path(config['global_hdfs_data_dir'])

        structures[host_name] = {'containers': host_containers, 'cpu': str(cpu_per_node), 'mem': str(mem_per_node), 'energy': str(energy_per_node), 'disks': server_disk_dict}
        number_of_hosts -= 1

    for i in range(0,number_of_hosts,1):
        host_name = 'host' + str(i)
        host_containers = create_container_list(host_name,number_of_containers_per_node)
        structures[host_name] = {'containers': host_containers, 'cpu': str(cpu_per_node), 'mem': str(mem_per_node), 'energy': str(energy_per_node), 'disks': disks_dict}

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
        write_container_list(structures[host]['containers'],host,structures[host]['cpu'],structures[host]['mem'],structures[host]['disks'],structures[host]['energy'])

def update_inventory_hosts_containers(number_of_containers_per_node):

    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)

    hostList = ansible_inventory.groups['nodes'].get_hosts()

    structures = {}

    for host in hostList:
        host_name = host.name
        host_containers = create_container_list(host_name,number_of_containers_per_node)
        structures[host_name] = {'containers': host_containers, 'cpu': host.vars['cpu'], 'mem': host.vars['mem'], 'energy': host.vars.get('energy'), 'disks': host.vars.get('disks')}

    print(structures)

    for host in structures:
        write_container_list(structures[host]['containers'],host,structures[host]['cpu'],structures[host]['mem'],structures[host]['disks'],structures[host]['energy'])

def create_container_list(host_name,number_of_containers_per_node):

    host_containers = []

    for i in range(0,number_of_containers_per_node,1):
        cont_name = 'cont' + str(i)
        host_containers.append(host_name + host_container_separator + cont_name)

    return host_containers

if __name__ == "__main__":

    config_file = scriptDir + "/../config/config.yml"

    with open(config_file, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    # Disks
    if config['disk_capabilities']:
        hdd_disks_per_host = config['hdd_disks_per_host']
        hdd_disks_path_list = config['hdd_disks_path_list'].split(",")
        ssd_disks_per_host = config['ssd_disks_per_host']
        ssd_disks_path_list = config['ssd_disks_path_list'].split(",")
        create_lvm = config['create_lvm']
        lvm_path = config['lvm_path']
        disks_dict = get_disks_dict(hdd_disks_per_host, hdd_disks_path_list, ssd_disks_per_host, ssd_disks_path_list, create_lvm, lvm_path)
    else:
        disks_dict = None

    virtual_mode = config['virtual_mode']
    server_ip = config['server_ip']

    update_server_ip(server_ip)

    if (virtual_mode):
        write_inventory_from_conf(config, disks_dict)
    else: 
        update_inventory_hosts_containers(config['number_of_containers_per_node'])
