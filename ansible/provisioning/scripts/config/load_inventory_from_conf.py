#!/usr/bin/env python
import sys
import os
import yaml

scriptDir = os.path.realpath(os.path.dirname(__file__))
CONFIG_FILE = scriptDir + "/../../config/config.yml"

from serverlessyarn_utils.manage_inventory import AnsibleYamlInventory, get_disks_dict, resolve_disk_path, create_container_list

## Auxiliary methods
def create_resource_dict(config):

    return {
        'cpu': config['cpus_per_host'],
        'mem': config['memory_per_host'],
        'energy': config['energy_per_host'] if config['power_budgeting'] else None,
        'disks': get_disks_dict(
                hdd_disks=config['hdd_disks_per_host'],
                hdd_disks_path_list=config['hdd_disks_path_list'].split(","),
                ssd_disks=config['ssd_disks_per_host'],
                ssd_disks_path_list=config['ssd_disks_path_list'].split(","),
                create_lvm=config['create_lvm'],
                lvm_path=config['lvm_path']
            ) if config['disk_capabilities'] else {},
        'containers': []
    }

def update_disks_bandwidths(previous_inventory, hostname, resources):
    """
    Update bandwidths of known disks with old measurements
    """
    previous_disks = previous_inventory.get_disks(hostname)
    for disk in resources["disks"]:
        if previous_disks and disk in previous_disks:
            for resource in ['read_bw', 'write_bw']:
                if resource in previous_disks[disk]:
                    resources["disks"][disk][resource] = previous_disks[disk][resource]

def main(flags):

    # Currently available flags = ["reset_disks"]

    # Load config
    with open(CONFIG_FILE, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    # Get hostnames
    if config.get('hostnames', None):
        hostnames = config['hostnames'].split(',')
    else:
        raise Exception("Error in configuration: 'hostnames' key does not exist or has null value. It should have been overriden during Vagrant or SLURM startup")

    # Get two copies of the inventory, one for changes and another one to read old parameters
    # (e.g., disk bandwidth when 'reset_disks' is disabled)
    previous_inventory = AnsibleYamlInventory()
    inventory = AnsibleYamlInventory()
    inventory.clean_inventory()

    # Add server
    server_name = hostnames.pop(0)
    inventory.add_server(host_ip=config['server_ip'], ansible_host=server_name)

    # Get relevant config parameters to build inventory
    number_of_hosts = config['number_of_hosts']
    server_as_host = config['server_as_host']
    number_of_containers_per_node = config['number_of_containers_per_node']

    # Set default resources for hosts
    default_resources = create_resource_dict(config)
    if not "reset_disks" in flags:
        update_disks_bandwidths(previous_inventory=previous_inventory, hostname=None, resources=default_resources)

    # Add group for hosts
    inventory.add_node_group(resources=default_resources)

    # Add hosts
    ## Add server as host (if enabled)
    if server_as_host:
        host_containers = create_container_list(server_name, number_of_containers_per_node)
        server_resources = create_resource_dict(config)
        server_resources['cpu'] = config['cpus_server_node']
        server_resources['mem'] = config['memory_server_node']

        ## Add specific disk for HDFS namenode when also acting as frontend
        if config['global_hdfs'] and config['disk_capabilities']:
            disk_name = config['global_hdfs_disk_name']
            server_resources['disks'][disk_name] = {}
            server_resources['disks'][disk_name]['path'] = resolve_disk_path(config['global_hdfs_data_dir'])

        if not "reset_disks" in flags:
            update_disks_bandwidths(previous_inventory=previous_inventory, hostname=server_name, resources=server_resources)

        inventory.add_node(hostname=server_name, resources=server_resources, containers=host_containers)
        number_of_hosts -= 1

    ## Add regular hosts
    for i in range(0, number_of_hosts):
        host_name = hostnames[i]
        host_containers = create_container_list(host_name, number_of_containers_per_node)
        host_resources = create_resource_dict(config)

        if not "reset_disks" in flags:
            update_disks_bandwidths(previous_inventory=previous_inventory, hostname=host_name, resources=host_resources)

        inventory.add_node(hostname=host_name, resources=host_resources, containers=host_containers)

    # Save all changes
    inventory.save()

if __name__ == "__main__":

    flags = []
    if (len(sys.argv) > 1):
        flags = sys.argv[1:]

    main(flags)