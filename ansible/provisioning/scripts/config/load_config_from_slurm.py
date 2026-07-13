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

def getNodesCpus():

    #export CPUS_PER_NODE=`grep "^physical id" /proc/cpuinfo | sort -u | wc -l`     # CPUs per node
    #export CORES_PER_CPU=`grep "^core id" /proc/cpuinfo | sort -u | wc -l` # Cores per CPU
    #export CORES_PER_NODE=$(( $CPUS_PER_NODE * $CORES_PER_CPU ))   # Cores per node

    cpus_per_node_string = os.getenv('SLURM_JOB_CPUS_PER_NODE')
    if cpus_per_node_string != "":
        try:
            cpus_per_node = int(cpus_per_node_string)
        except ValueError:
            # We assume that it has format: 16(x2)
            #formatted_cpus = cpus_per_node_string.replace('x','*').replace("(","").replace(")","")
            #cpus_per_node = eval(formatted_cpus)
            formatted_cpus = re.sub("[\(\[].*?[\)\]]", "", cpus_per_node_string)
            cpus_per_node = int(formatted_cpus)

            # TODO: check if the system actually has HT
            # adjust to hyperthreading system
            cpus_per_node = cpus_per_node * 2
    else:
        raise Exception("Can't get node CPUs")

    return cpus_per_node

# Not used ATM
def getNodesMemory_scontrol(server):
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

    return allocMem

def getNodesMemory():

    #export MEMORY_PER_NODE=$((`grep MemTotal /proc/meminfo | awk '{print $2}'`/1024))	# Total Memory per node

    job = os.getenv('SLURM_JOB_ID')
    #paramater_list = "JobID,AllocCPUs,MaxRSSNode,NCPUs,ReqMem,MinCPUNode"
    paramater_list = "ReqMem"

    #rc = subprocess.Popen(["sacct", "-j", job, "--format={0}".format(paramater_list), "-n", "-P", "--units", "M"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rc = subprocess.Popen(["grep", "MemTotal", "/proc/meminfo"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #rc = subprocess.Popen(["awk", "'{print $2}'"], stdin=get_mem.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, err = rc.communicate()
    #memlist = output.decode().splitlines()
    memlist = re.findall(r'\b\d+\b', output.decode())

    memory_factor = 0.9

    try:
        allocMem_string = memlist[0]

        # We assume it has format: 3800Mc
        #allocMem = int(re.sub(r'[^0-9]', '', allocMem_string))

        allocMem = int(int(int(re.sub(r'[^0-9]', '', allocMem_string)) / 1024) * memory_factor)

    except IndexError:
        raise Exception("Can't get node Memory")

    return allocMem

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

    # Read 'server_as_host' parameter (found in 02-hosts.yml)
    with open(config_file_list[1], "r") as f:
        server_as_host = yaml.load(f, Loader=yaml.FullLoader)['server_as_host']

    # Get deployment info from SLURM environment
    server, server_ip, hosts = getHostList(server_as_host)
    cpus_per_node = getNodesCpus()
    memory_per_node = getNodesMemory()

    # Update config
    update_config_file(config_file_list, server_ip, hosts, cpus_per_node, memory_per_node)
