#!/usr/bin/python

from pathlib import Path
from ruamel.yaml import YAML
import os
import subprocess
import re
import yaml
import socket

def getHostList():
    rc = subprocess.Popen(["scontrol", "show", "hostnames"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, err = rc.communicate()
    hostlist = output.decode().splitlines()
    server = hostlist[0]
    server_ip = socket.gethostbyname(server)

    print("Server: {0}".format(server))
    print("Client nodes: {0}".format(hostlist))

    return server, server_ip, hostlist

SMT_MODES = ["disabled", "enabled", "hybrid"]

def getNodesCpus(smt_mode):

    if smt_mode not in SMT_MODES:
        raise Exception("Invalid value for 'smt_mode': {0}. Valid values are: {1}".format(smt_mode, ", ".join(SMT_MODES)))

    # Both 'enabled' and 'hybrid' modes use all the logical cores at platform level (they only differ at app level)
    use_smt = smt_mode in ["enabled", "hybrid"]

    # 1: Get CPUs scheduled by SLURM
    cpus_per_node_string = os.getenv('SLURM_JOB_CPUS_PER_NODE')
    if cpus_per_node_string != "":
        try:
            cpus_per_node = int(cpus_per_node_string)
        except ValueError:
            # We assume that it has format: 16(x2)
            formatted_cpus = re.sub("[\(\[].*?[\)\]]", "", cpus_per_node_string)
            cpus_per_node = int(formatted_cpus)

        # 2: Check SMT
        # Read /sys/devices/system/cpu/smt/active to check if smt is running on the system
        effective_smt_mode = "disabled"
        try:
            with open("/sys/devices/system/cpu/smt/active", "r") as f:
                smt_active = int(f.read().strip()) > 0
        except:
            smt_active = False

        if smt_active:
            # 3: Check the actual resources in the machine to check if SLURM is reporting SMT
            logical_cores = os.cpu_count()
            physical_cores = len(set(l for l in subprocess.check_output(["lscpu", "-p=CORE,SOCKET"], text=True).splitlines() if not l.startswith("#")))

            ## 3.1: SMT is being reported --> reduce the cores to the physical cores to disable SMT
            if cpus_per_node > physical_cores:
                if not use_smt:
                    cpus_per_node = physical_cores

            ## 3.2: SMT is not being reported, and all physical cores are scheduled --> increase the cores to the logical ones to enable SMT
            elif cpus_per_node == physical_cores:
                if use_smt:
                    cpus_per_node = logical_cores

            ## 3.3: Else, SMT is not being reported, but not all cores are scheduled --> just use the scheduled cores
            elif use_smt:
                print("WARNING: SMT is active on the hosts, but SLURM did not schedule all the physical cores nor reported "
                      "their logical cores. SMT mode '{0}' can't be applied, so it will be disabled".format(smt_mode))

            # 4: SMT is used by the platform only if more cores than the physical ones are finally used
            if cpus_per_node > physical_cores:
                effective_smt_mode = smt_mode

        elif use_smt:
            print("WARNING: SMT is not active on the hosts. SMT mode '{0}' can't be applied, so it will be disabled".format(smt_mode))
    else:
        raise Exception("Can't get node CPUs")

    print("CPUs per node: {0} (SMT mode: {1})".format(cpus_per_node, effective_smt_mode))

    return cpus_per_node, effective_smt_mode

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

def update_config_file(config_file_list, server_ip, hosts, cpus_per_node, effective_smt_mode, memory_per_node, server_as_host=False):

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
    number_of_hosts = len(hosts) if server_as_host else len(hosts) - 1
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
        'hostnames': ','.join(hosts),
        'effective_smt_mode': effective_smt_mode
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
        smt_mode = hosts_config['smt_mode']
        memory_factor = hosts_config['memory_factor']

    # Get deployment info from SLURM environment
    server, server_ip, hosts = getHostList()
    cpus_per_node, effective_smt_mode = getNodesCpus(smt_mode)
    memory_per_node = getNodesMemory(server, memory_factor)

    # Update config
    update_config_file(config_file_list, server_ip, hosts, cpus_per_node, effective_smt_mode, memory_per_node, server_as_host)
