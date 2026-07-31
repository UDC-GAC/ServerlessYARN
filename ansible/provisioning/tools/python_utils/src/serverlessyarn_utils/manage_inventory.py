#!/usr/bin/env python
import os
import copy
from ruamel.yaml import YAML

scriptDir = os.path.realpath(os.path.dirname(__file__))
INVENTORY_FILE = scriptDir + "/../../../../../ansible.inventory.yml"

SERVER_GROUP_NAME = "platform_management"
SERVER_INVENTORY_NAME = "platform_server"
HOST_GROUP_NAME = "nodes"
EMPTIABLE_VARS = ["disks", "containers"] ## variables that may appear in inventory as empty (e.g., 'containers = []', 'disks = {}')
HOST_CONTAINER_SEPARATOR = "-"

class AnsibleYamlInventory:
    def __init__(self, filepath=INVENTORY_FILE):
        self.filepath = filepath
        self.yaml = YAML()
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.data = self._load()

    # Load and save inventory file
    def _load(self):
        if os.path.exists(self.filepath) and os.path.getsize(self.filepath) > 0:
            with open(self.filepath, 'r') as f:
                return self.yaml.load(f)
        return {}

    def save(self):
        """Save changes in the file."""
        with open(self.filepath, 'w') as f:
            self.yaml.dump(self.data, f)

    # Basic inventory managing methods
    def _add_group(self, group_name, group_vars=None):
        inventory = self.data

        # Create group if does not exist
        if group_name not in inventory:
            inventory[group_name] = {"hosts": {}}

        # Add hosts dictionary if does not exist
        if inventory[group_name].get("hosts") is None:
            inventory[group_name]["hosts"] = {}

        # Add group default variables
        if group_vars:
            for var in group_vars:
                ## Discard null variables
                if group_vars[var] or var in EMPTIABLE_VARS:
                    # Add vars dictionary if does not exist yet
                    if inventory[group_name].get("vars") is None:
                        inventory[group_name]["vars"] = {}
                    inventory[group_name]["vars"][var] = group_vars[var]

    def _add_host_to_group(self, group_name, hostname, host_vars=None):
        inventory = self.data
        self._add_group(group_name)

        # Add host if does not exist
        if hostname not in inventory[group_name]["hosts"]:
            inventory[group_name]["hosts"][hostname] = {}

        for var in host_vars:
            self._set_host_var(group_name=group_name, key=var, value=host_vars[var], hostname=hostname)

    def _remove_host(self, group_name, hostname):
        inventory = self.data

        if group_name in inventory:
            inventory[group_name].pop(hostname, None)

    def _get_host_var(self, group_name, key, hostname=None):
        inventory = self.data

        if not hostname or inventory[group_name]["hosts"].get(hostname, {}).get(key, None) is None:
            # Try to get the default group value
            return inventory[group_name]["vars"].get(key, None)
        else:
            return inventory[group_name]["hosts"][hostname].get(key, None)

    def _set_host_var(self, group_name, key, value, hostname=None):

        inventory = self.data

        if not hostname:
            if inventory[group_name].get("vars") is None:
                inventory[group_name]["vars"] = {}
            inventory[group_name]["vars"][key] = value
        else:
            inventory[group_name]["hosts"][hostname].pop(key, None)

            # Discard null variables (unless nullable)
            if not value and (key not in EMPTIABLE_VARS or "vars" not in inventory[group_name] or key not in inventory[group_name]["vars"]):
                return

            # Add host variable only if different from group default
            if "vars" not in inventory[group_name] or key not in inventory[group_name]["vars"] or value != inventory[group_name]["vars"][key]:
                inventory[group_name]["hosts"][hostname][key] = value

    # Common methods to use in external scripts
    ## Getters
    def get_node_hostnames(self):
        inventory = self.data
        return list(
            inventory[HOST_GROUP_NAME].get('hosts', {}).keys()
        ) if HOST_GROUP_NAME in inventory else []

    def get_node_resource(self, resource, hostname):
        try:
            host_var = self._get_host_var(group_name=HOST_GROUP_NAME, key=resource, hostname=hostname)
        except KeyError:
            raise Exception(f"Host {hostname} did not match with any of the existing hosts in inventory")

        if host_var is not None:
            if resource == 'containers':
                ## Return a shallow copy, since no nested lists or dicts are in a container list
                host_var = copy.copy(host_var)
            elif resource == 'disks':
                ## Return a deepcopy
                host_var = copy.deepcopy(host_var)

        return host_var

    def get_server_hostname(self):
        try:
            return self._get_host_var(group_name=SERVER_GROUP_NAME, key="ansible_host", hostname=SERVER_INVENTORY_NAME)
        except KeyError:
            raise Exception(f"{SERVER_INVENTORY_NAME} host is missing from inventory")

    def get_containers(self, hostname):
        current_containers = self.get_node_resource(resource="containers", hostname=hostname)
        return current_containers if current_containers is not None else []

    def get_disks(self, hostname):
        current_disks = self.get_node_resource(resource="disks", hostname=hostname)
        return current_disks if current_disks is not None else {}

    ## Adds
    def add_server(self, host_ip, ansible_host):

        host_vars = {
            "host_ip": host_ip,
            "ansible_host": ansible_host
        }
        self._add_host_to_group(group_name=SERVER_GROUP_NAME, hostname=SERVER_INVENTORY_NAME, host_vars=host_vars)

    def add_node_group(self, resources=None):
        self._add_group(group_name=HOST_GROUP_NAME, group_vars=resources)

    def add_node(self, hostname, resources, containers):

        host_vars = resources
        host_vars["containers"] = containers

        self._add_host_to_group(group_name=HOST_GROUP_NAME, hostname=hostname, host_vars=host_vars)

    def add_container(self, hostname, container):
        try:
            current_containers = self.get_node_resource(resource="containers", hostname=hostname)
        except KeyError:
            raise Exception(f"Host {hostname} did not match with any of the existing hosts in inventory")

        if current_containers is None: current_containers = []
        current_containers.append(container)
        self._set_host_var(group_name=HOST_GROUP_NAME, key="containers", value=current_containers, hostname=hostname)

    def add_containers(self, hostname, containers):
        current_containers = self.get_node_resource(resource="containers", hostname=hostname)
        if current_containers is None: current_containers = []
        current_containers.extend(containers)
        self._set_host_var(group_name=HOST_GROUP_NAME, key="containers", value=current_containers, hostname=hostname)

    def add_disks(self, hostname, disks):
        current_disks = self.get_node_resource(resource="disks", hostname=hostname)
        if current_disks is None: current_disks = {}
        current_disks.update(disks)
        self._set_host_var(group_name=HOST_GROUP_NAME, key="disks", value=current_disks, hostname=hostname)

    ## Removes
    def remove_node(self, hostname):
        self._remove_host(HOST_GROUP_NAME, hostname)

    def remove_container(self, hostname, container):
        current_containers = self.get_node_resource(resource="containers", hostname=hostname)
        if current_containers and container in current_containers:
            current_containers.remove(container)
        self._set_host_var(group_name=HOST_GROUP_NAME, key="containers", value=current_containers, hostname=hostname)

    def clean_inventory(self):
        inventory = self.data
        inventory.clear()

    ## Updates/Setters
    def update_disk(self, hostname, disk, new_disk_info):
        current_disks = self.get_node_resource(resource="disks", hostname=hostname)
        if current_disks is None: current_disks = {}
        current_disks[disk].update(new_disk_info)
        self._set_host_var(group_name=HOST_GROUP_NAME, key="disks", value=current_disks, hostname=hostname)


## Static auxiliary methods for external scripts
def create_container_list(host_name, number_of_containers, first_index=0):
    """
    Returns a container list such as "[host0-cont0, host0-cont1]"
    """

    host_containers = []

    for i in range(first_index, number_of_containers+first_index, 1):
        cont_name = 'cont' + str(i)
        host_containers.append(host_name + HOST_CONTAINER_SEPARATOR + cont_name)

    return host_containers

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