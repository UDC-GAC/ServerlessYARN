import os
import json
import sys
import time
import yaml
import requests
import subprocess
from datetime import datetime, timedelta
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager

POLLING_FREQUENCY = 5

script_path = os.path.abspath(__file__)
provisioning_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
config_file = f"{provisioning_dir}/config/config.yml"
inventory_file = f"{provisioning_dir}/../ansible.inventory"

def get_nodes():
    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)
    return ansible_inventory.get_groups_dict()['nodes']

## CAUTION! Passwordless SSH is mandatory
def get_containers_from_nodes(singularity_command_alias, nodes):
    containers = {}
    for node in nodes:
        process = subprocess.Popen(["ssh", node, "sudo", singularity_command_alias, "instance", "list", "-j"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        containers[node] = json.loads(stdout)
    
    return containers

def set_container_names_by_pid(nodes, containers, container_name):
    for node in nodes:
        instances = containers[node]['instances']
        for instance in instances:
            pid = instance['pid']
            name = instance['instance']
            if pid not in container_name:
                container_name[pid] = name
    return container_name

if __name__ == "__main__":

    if len(sys.argv) < 2:
        raise Exception("Missing some arguments: send_power_opentsdb.py <singularity_command_alias> <smartwatts_output_dir>")

    singularity_command_alias = sys.argv[1]
    smartwatts_output = sys.argv[2]

    with open(config_file, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    # Get containers for each node
    nodes = get_nodes()
    containers = get_containers_from_nodes(singularity_command_alias, nodes)
    containers_by_pid = set_container_names_by_pid(nodes, containers, {})
    print(containers_by_pid)

    # Get session to OpenTSDB
    opentsdb_url = "http://{0}:{1}/api/put".format(config['server_ip'], config['opentsdb_port'])
    headers = {'Content-Type': 'application/json'}
    session = requests.Session()

    # Read SmartWatts output and get targets
    output_file = {}
    last_read_position = {}
    while True:
        new_targets = False
        for target_dir in os.listdir(smartwatts_output):
            target_name = target_dir[7:] # Remove "sensor-"

            # If target is an Apptainer container we get his real name
            if target_name.startswith("apptainer"):
                pid = int(target_name[10:])
                if pid in containers_by_pid:
                    target_name = containers_by_pid[pid]

            if target_name not in output_file: # New targets
                new_targets = True
                print(f"Found new target with name {target_name}. Registered.")
                output_file[target_name] = f"{smartwatts_output}/{target_dir}/PowerReport.csv"
                last_read_position[target_name] = 0

            with open(output_file[target_name], 'r') as file:
                # If file is empty, skip
                if os.path.getsize(output_file[target_name]) <= 0:
                    continue

                # Skip header
                file.seek(last_read_position[target_name])
                if last_read_position[target_name] == 0:
                    next(file)

                lines = file.readlines()
                if len(lines) == 0:
                    print("There aren't new lines to process for target {0}".format(target_name))
                    continue

                print("Processing {0} lines for target {1}".format(len(lines), target_name))
                last_read_position[target_name] = file.tell()
                data = {"metric": "structure.energy.usage", "tags": {"host": target_name}}

                # line example: <timestamp> <sensor> <target> <value> ...
                for line in lines:
                    fields = line.strip().split(',')
                    num_fields = len(fields)

                    if num_fields < 4:
                        raise Exception("Missing some fields in SmartWatts output for "
                                        "target {0} ({1} out of 4 expected fields)".format(target_name, num_fields))

                    # Add 2 hours to the timestamp
                    # For some reason SmartWatts timestamps are set two hours ahead (even taking into account the timezone)
                    timestamp = datetime.fromtimestamp(int(fields[0]) / 1000) + timedelta(hours=2)
                    data["timestamp"] = int(timestamp.timestamp() * 1000)
                    data["value"] = float(fields[3])

                    
                    r = session.post(opentsdb_url, data=json.dumps(data), headers=headers)
                    if r.status_code != 204:
                        print("Error while sending target {0} metrics to OpenTSDB. Sent data: {1}".format(target_name, data))
                        r.raise_for_status()
        
        # If there are new targets, new containers may have been created
        if new_targets:
            nodes = get_nodes()
            containers = get_containers_from_nodes(singularity_command_alias, nodes)
            containers_by_pid = set_container_names_by_pid(nodes, containers, containers_by_pid)
            print(containers_by_pid)

        time.sleep(POLLING_FREQUENCY)
