import os
import re
import json
import time
import redis

from django.conf import settings

import ui.run_playbooks as run_playbooks

## Data locality support for the 'Data-locality' allocation policy
# Computes a locality score for each host, i.e., how close it is to the data that an app will read from the global HDFS.
# The following sources are used, in order of preference:
#   1) "input_data": block locations of the input data explicitly provided by the user (only available in 'isolated' mode)
#   2) "deployment_registry": previous deployments of the app it depends on (if any) and of any app (including other executions
#       of the same app), as some apps produce the data consumed by others and HDFS writes the first replica of each block on the
#       host of the writer
#   3) "global_datanodes": hosts running a global HDFS datanode, as they are the only ones that may hold data

redis_server = redis.StrictRedis()
registry_lock_key = "data_locality_registry_lock"

DEFAULT_REGISTRY_FILE = "{{ installation_path }}/data_locality_registry.json"
DEFAULT_HISTORY_SIZE = 20
DEFAULT_HISTORY_DECAY = 0.8
DEFAULT_DEPENDENCY_WEIGHT = 2


## Deployment registry
# Format: {"deployments": [{"app": app_name, "timestamp": ..., "hosts": {host_name: number_of_workers, ...}, ...}, ...]} (most recent deployments first)
def get_registry_path():
    registry_file = settings.VARS_CONFIG.get('data_locality_registry_file', DEFAULT_REGISTRY_FILE)
    return registry_file.replace("{{ installation_path }}", settings.INSTALLATION_PATH)

def load_registry():
    registry_path = get_registry_path()
    empty_registry = {"deployments": []}
    if not os.path.exists(registry_path):
        return empty_registry

    try:
        with open(registry_path, "r") as f:
            registry = json.load(f)
    except (OSError, ValueError) as e:
        print("[DATA LOCALITY] Error reading deployment registry {0}: {1}".format(registry_path, str(e)))
        return empty_registry

    if not isinstance(registry, dict) or not isinstance(registry.get("deployments"), list):
        print("[DATA LOCALITY] Unknown format in deployment registry {0}, starting a new one".format(registry_path))
        return empty_registry

    return registry

def save_registry(registry):
    registry_path = get_registry_path()
    os.makedirs(os.path.dirname(registry_path), exist_ok=True)

    ## Write to a temporary file first to avoid leaving a corrupted registry if something fails
    tmp_path = registry_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(registry, f, indent=2)
    os.replace(tmp_path, registry_path)

def record_deployment(app_name, new_containers, deployment_info=None):
    # new_containers example = {'host0': {'regular': 2, 'rm-nn': 1}, 'host1': {'regular': 1, 'irregular': 1}}
    # Only workers are recorded, since the 'rm-nn' container does not read or write data from HDFS
    worker_hosts = {}
    for host, host_containers in new_containers.items():
        number_of_workers = host_containers.get("regular", 0) + host_containers.get("irregular", 0)
        if number_of_workers > 0:
            worker_hosts[host] = number_of_workers

    if not worker_hosts:
        return

    entry = {"app": app_name, "timestamp": time.time(), "hosts": worker_hosts}
    if deployment_info:
        entry.update({key: value for key, value in deployment_info.items() if value})

    history_size = int(settings.PLATFORM_CONFIG.get('data_locality_history_size', DEFAULT_HISTORY_SIZE))
    with redis_server.lock(registry_lock_key, timeout=60):
        registry = load_registry()
        registry["deployments"].insert(0, entry)
        del registry["deployments"][history_size:]
        save_registry(registry)

def clear_registry():
    with redis_server.lock(registry_lock_key, timeout=60):
        save_registry({"deployments": []})


## Locality scores
def get_registry_scores(dependency_app=None):
    deployments = load_registry()["deployments"]
    scores = {}

    def add_entry_scores(entry, weight):
        # Each deployment distributes its weight among its hosts proportionally to the number of workers deployed on them
        total_workers = sum(entry['hosts'].values())
        for host, number_of_workers in entry['hosts'].items():
            scores[host] = scores.get(host, 0) + weight * number_of_workers / total_workers

    ## Latest deployment of the app it depends on (e.g., previous stage of a pipeline), whose output is likely the input of this app
    dependency_entry = None
    if dependency_app:
        dependency_entry = next((entry for entry in deployments if entry.get('app') == dependency_app), None)
    if dependency_entry:
        dependency_weight = float(settings.PLATFORM_CONFIG.get('data_locality_dependency_weight', DEFAULT_DEPENDENCY_WEIGHT))
        add_entry_scores(dependency_entry, dependency_weight)

    ## Previous deployments of any app (including the same one), as some apps produce the data consumed by others
    # More weight is given to the most recent ones (weight = decay ^ age) and the weights of the whole history are normalised to sum 1
    decay = float(settings.PLATFORM_CONFIG.get('data_locality_history_decay', DEFAULT_HISTORY_DECAY))
    history = [entry for entry in deployments if entry is not dependency_entry]
    history_weights = [decay ** age for age in range(len(history))]
    total_weight = sum(history_weights)
    for entry, weight in zip(history, history_weights):
        add_entry_scores(entry, weight / total_weight)

    return scores

def get_input_data_scores(locality_info):
    # Score = bytes of input data that can be read locally from each host (i.e., bytes of the blocks with a replica on that host)
    datanodes = locality_info['datanodes'] # {datanode_container_name: host_name}

    blocks_output, resolutions_output = run_playbooks.get_hdfs_block_locations(
        locality_info['namenode_host'], locality_info['namenode_container_name'], locality_info['global_input'], list(datanodes.keys()))

    ## Map datanode addresses to hosts
    # HDFS reports datanodes by IP address, although they are also mapped by name in case HDFS is configured to use hostnames
    address_to_host = dict(datanodes)
    for line in resolutions_output.splitlines():
        fields = line.split()
        for name in fields[1:]:
            for datanode_name in [name, name.split('.')[0]]:
                if datanode_name in datanodes:
                    address_to_host[fields[0]] = datanodes[datanode_name]

    ## Aggregate block sizes per host
    scores = {}
    for line in blocks_output.splitlines():
        block_length = re.search(r'len=(\d+)', line)
        if not block_length:
            continue

        # Datanodes appear after the block length as 'address:port', e.g., "[DatanodeInfoWithStorage[10.22.0.3:9866,DS-...,DISK], ...]"
        replica_hosts = set()
        for address in re.findall(r'([A-Za-z0-9_.\-]+):\d+', line[block_length.end():]):
            if address in address_to_host:
                replica_hosts.add(address_to_host[address])

        for host in replica_hosts:
            scores[host] = scores.get(host, 0) + int(block_length.group(1))

    return scores

def get_data_locality_scores(app_name, locality_info, dependency_app=None):
    datanode_hosts = {}
    for host in locality_info['datanodes'].values():
        datanode_hosts[host] = datanode_hosts.get(host, 0) + 1

    ## 1) Input data explicitly provided by the user
    if locality_info.get('global_input', "") != "":
        try:
            scores = get_input_data_scores(locality_info)
        except Exception as e:
            print("[DATA LOCALITY] Error getting block locations of {0} for app {1}: {2}".format(locality_info['global_input'], app_name, str(e)))
            scores = {}

        if scores:
            return scores, "input_data"
        print("[DATA LOCALITY] No block locations found for {0}, falling back to the deployment registry for app {1}".format(locality_info['global_input'], app_name))

    ## 2) Deployment registry
    # Only hosts running a global datanode are considered, since the rest of hosts cannot hold any data
    scores = {host: score for host, score in get_registry_scores(dependency_app).items() if host in datanode_hosts}
    if scores:
        return scores, "deployment_registry"

    ## 3) Hosts running a global datanode, weighted by their number of datanodes
    return datanode_hosts, "global_datanodes"
