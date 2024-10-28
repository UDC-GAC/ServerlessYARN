# /usr/bin/python
import sys
import yaml
import requests
import json
from bs4 import BeautifulSoup
from copy import deepcopy

rescaler_port = "8000"


base_container_to_API = dict(
    container = dict(
        name = "base_container",
        resources = dict(
            cpu = dict(),
            mem = dict()
        ),
        host_rescaler_ip = "base_host",
        host_rescaler_port= rescaler_port,
        host = "base_host",
        guard = True,
        subtype ="container"
    ),
    limits = dict(
        resources = dict()
    )
)

# usage example: add_containers_API_v3.py [{'container_name': 'host1-cont1', 'host': 'host1', 'cpu_max': 200, 'cpu_min': 50, 'mem_max': 2048, 'mem_min': 1024, 'energy_max': 100, 'energy_min': 30, 'cpu_boundary': 25, 'mem_boundary': 256, 'energy_boundary': 10, 'disk': 'hdd_0', 'disk_path: '$HOME/hdd', 'disk_max': 200, 'disk_min': 50}, {'container_name': 'host1-cont1'...}] config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 2):
        containers = json.loads(sys.argv[1].replace('\'','"'))
        with open(sys.argv[2], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        orchestrator_url = "http://{0}:{1}".format(config['server_ip'], config['orchestrator_port'])
        headers = {'Content-Type': 'application/json'}

        session = requests.Session()

        ## Add containers
        for cont in containers:
            cont_resources = ["cpu", "mem"]
            full_url = "{0}/structure/container/{1}".format(orchestrator_url, cont['container_name'])

            put_field_data = deepcopy(base_container_to_API)

            ## Container info
            put_field_data['container']["name"] = cont['container_name']
            put_field_data['container']['host_rescaler_ip'] = cont['host']
            put_field_data['container']['host'] = cont['host']

            put_field_data['container']['resources']["cpu"]["max"] = int(cont['cpu_max'])
            put_field_data['container']['resources']["cpu"]["current"] = int(cont['cpu_max'])
            put_field_data['container']['resources']["cpu"]["min"] = int(cont['cpu_min'])
            put_field_data['container']['resources']["cpu"]["guard"] = True

            put_field_data['container']['resources']["mem"]["max"] = int(cont['mem_max'])
            put_field_data['container']['resources']["mem"]["current"] = int(cont['mem_max'])
            put_field_data['container']['resources']["mem"]["min"] = int(cont['mem_min'])
            put_field_data['container']['resources']["mem"]["guard"] = True

            # Energy
            if 'power_budgeting' in config and config['power_budgeting']:
                cont_resources.append("energy")
                put_field_data['container']['resources']["energy"] = dict()
                put_field_data['container']['resources']["energy"]["max"] = int(cont['energy_max'])
                put_field_data['container']['resources']["energy"]["current"] = int(cont['energy_max'])
                put_field_data['container']['resources']["energy"]["min"] = int(cont['energy_min'])
                put_field_data['container']['resources']["energy"]["guard"] = True

            # Disk
            if 'disk' in cont and config['disk_capabilities'] and config['disk_scaling']:
                cont_resources.append("disk")
                put_field_data['container']['resources']["disk"] = {}
                put_field_data['container']['resources']["disk"]["name"] = cont['disk']
                put_field_data['container']['resources']["disk"]["path"] = cont['disk_path']
                put_field_data['container']['resources']["disk"]["max"] = int(cont['disk_max'])
                put_field_data['container']['resources']["disk"]["current"] = int(cont['disk_min'])
                put_field_data['container']['resources']["disk"]["min"] = int(cont['disk_min'])
                put_field_data['container']['resources']["disk"]["guard"] = True

            ## Limits
            for res in cont_resources:
                put_field_data['limits']["resources"][res] = {}
                if cont[f'{res}_boundary'] == 0:
                    put_field_data['limits']["resources"][res]["boundary"] = int(config[f'{res}_boundary'])
                else:
                    put_field_data['limits']["resources"][res]["boundary"] = int(cont[f'{res}_boundary'])

            r = session.put(full_url, data=json.dumps(put_field_data), headers=headers)

            if r != "" and r.status_code != requests.codes.ok:
                soup = BeautifulSoup(r.text, features="html.parser")
                if r.status_code == 400 and "already exists" in soup.get_text().strip():
                    # Container already exists
                    print("Container {0} already exists".format(cont['container_name']))
                else:
                    raise Exception("Error adding container {0}: {1} | Data: {2}".format(cont['container_name'], soup.get_text().strip(), put_field_data))
