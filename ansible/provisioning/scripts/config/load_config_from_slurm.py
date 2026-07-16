#!/usr/bin/python

from pathlib import Path
from ruamel.yaml import YAML
import os
import subprocess
import re
import yaml
import socket

def getHostList(server_as_host=False):
    rc = subprocess.Popen(["scontrol", "show", "hostnames"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, err = rc.communicate()
    hostlist = output.decode().splitlines()
    server = hostlist[0]
    if not server_as_host:
        hostlist.pop(0)

    server_ip = socket.gethostbyname(server)

    print("Server: {0}".format(server))
    print("Client nodes: {0}".format(hostlist))

    return server, server_ip, hostlist

def getNodesCpus(disable_smt):

    cpus_per_node_string = os.getenv('SLURM_JOB_CPUS_PER_NODE')
    if cpus_per_node_string != "":
        try:
            cpus_per_node = int(cpus_per_node_string)
        except ValueError:
            # We assume that it has format: 16(x2)
            formatted_cpus = re.sub("[\(\[].*?[\)\]]", "", cpus_per_node_string)
            cpus_per_node = int(formatted_cpus)

        if not disable_smt:
            # Read /sys/devices/system/cpu/smt/active to check if smt is running on the system
            try:
                with open("/sys/devices/system/cpu/smt/active", "r") as f:
                    smt_active = int(f.read().strip()) > 0
            except:
                smt_active = False

            # Double the cores if SMT is enabled
            if smt_active:
                cpus_per_node = cpus_per_node * 2
    else:
        raise Exception("Can't get node CPUs")

    return cpus_per_node

def getNodesMemory(server, memory_factor):
    rc = subprocess.Popen(["scontrol", "-o", "show", "nodes", server], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, err = rc.communicate()
    itemlist = output.decode().split(" ")

    allocMem = ""
    for item in itemlist:
        if "AllocMem" in item:
            # We assume that it has format: AllocMem=40960
            allocMem = int(item.split("=")[1])
    if allocMem == "":
        raise Exception("Can't get node Memory")

    return int(allocMem * memory_factor)

def update_config_file(config_file_list, server_ip, hosts, cpus_per_node, memory_per_node):

    def update_config_fields(config_file, new_config):
        out = Path(config_file)
        data = yaml_utils.load(out)

        for field in new_config:
            try:
                data[field] = new_config[field]
            except KeyError:
                raise Exception("Configuration file {0} does not have the field {1}".format(config_file, field))

        yaml_utils.dump(data, out)

    cpus_server_node = cpus_per_node
    memory_server_node = memory_per_node
    number_of_hosts = len(hosts)
    cpus_per_host = cpus_per_node
    memory_per_host = memory_per_node

    ## Change required config modules
    yaml_utils = YAML()
    yaml_utils.default_flow_style = False
    yaml_utils.preserve_quotes = True

    ### 01-general.yml
    update_config_fields(config_file_list[0], {
        'virtual_mode': 'no',
        'container_engine': 'apptainer',
        'cgroups_version': 'v1'
    })

    ### 02-hosts.yml
    update_config_fields(config_file_list[1], {
        'server_ip': server_ip,
        'cpus_server_node': cpus_server_node,
        'memory_server_node': memory_server_node,
        'number_of_hosts': number_of_hosts,
        'cpus_per_host': cpus_per_host,
        'memory_per_host': memory_per_host,
        'hostnames': ','.join(hosts)
    })

    ### 07-containers.yml
    update_config_fields(config_file_list[6], {
        'number_of_containers_per_node': 0
    })

if __name__ == "__main__":

    scriptDir = os.path.realpath(os.path.dirname(__file__))

    # Setup list of config modules
    config_module_list = [
        "01-general.yml", "02-hosts.yml", "03-services.yml", "04-disk.yml",
        "05-power.yml", "06-hdfs.yml", "07-containers.yml", "08-apps.yml",
        "09-plugins.yml"
    ]
    config_file_list = []
    for module in config_module_list:
        config_file_list.append("{0}/../../config/modules/{1}".format(scriptDir, module))

    # Read host-related parameters
    with open(config_file_list[1], "r") as f:
        hosts_config = yaml.load(f, Loader=yaml.FullLoader)
        server_as_host = hosts_config['server_as_host']
        disable_smt = hosts_config['disable_ht']
        memory_factor = hosts_config['memory_factor']

    # Get deployment info from SLURM environment
    server, server_ip, hosts = getHostList(server_as_host)
    cpus_per_node = getNodesCpus(disable_smt)
    memory_per_node = getNodesMemory(server, memory_factor)

    # Update config
    update_config_file(config_file_list, server_ip, hosts, cpus_per_node, memory_per_node)
