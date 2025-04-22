# /usr/bin/python
import sys
import yaml
import requests
import json
import os
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

scriptDir = os.path.realpath(os.path.dirname(__file__))
sys.path.append(scriptDir + "/../../services/serverless_containers_web/ui")
from utils import request_to_state_db

# usage example: add_containers_API_v3.py [{'container_name': 'host1-cont1', 'host': 'host1', 'cpu_max': 200, 'cpu_min': 50, 'mem_max': 2048, 'mem_min': 1024, 'energy_max': 100, 'energy_min': 30, 'cpu_boundary': 25, 'mem_boundary': 256, 'energy_boundary': 10, 'disk': 'hdd_0', 'disk_path: '$HOME/hdd', 'disk_max': 200, 'disk_min': 50}, {'container_name': 'host1-cont1'...}] config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 2):
        containers = json.loads(sys.argv[1].replace('\'','"'))
        with open(sys.argv[2], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        orchestrator_url = "http://{0}:{1}".format(config['server_ip'], config['orchestrator_port'])
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
            put_field_data['container']['resources']["cpu"]["current"] = int(cont['cpu_min'])
            put_field_data['container']['resources']["cpu"]["min"] = int(cont['cpu_min'])
            put_field_data['container']['resources']["cpu"]["guard"] = True
            if 'cpu_weight' in cont: put_field_data['container']['resources']["cpu"]["weight"] = int(cont['cpu_weight'])

            put_field_data['container']['resources']["mem"]["max"] = int(cont['mem_max'])
            put_field_data['container']['resources']["mem"]["current"] = int(cont['mem_min'])
            put_field_data['container']['resources']["mem"]["min"] = int(cont['mem_min'])
            put_field_data['container']['resources']["mem"]["guard"] = True
            if 'mem_weight' in cont: put_field_data['container']['resources']["mem"]["weight"] = int(cont['mem_weight'])

            # Energy
            if 'power_budgeting' in config and config['power_budgeting']:
                cont_resources.append("energy")
                put_field_data['container']['resources']["energy"] = dict()
                put_field_data['container']['resources']["energy"]["max"] = int(cont['energy_max'])
                put_field_data['container']['resources']["energy"]["current"] = int(cont['energy_min'])
                put_field_data['container']['resources']["energy"]["min"] = int(cont['energy_min'])
                put_field_data['container']['resources']["energy"]["guard"] = True
                if 'energy_weight' in cont: put_field_data['container']['resources']["energy"]["weight"] = int(cont['energy_weight'])

            # Disk
            if 'disk' in cont and config['disk_capabilities'] and config['disk_scaling']:
                put_field_data['container']['resources']["disk"] = dict()
                put_field_data['container']['resources']["disk"]["name"] = cont['disk']
                put_field_data['container']['resources']["disk"]["path"] = cont['disk_path']
                for metric in ["disk_read", "disk_write"]:
                    cont_resources.append(metric)
                    put_field_data['container']['resources'][metric] = dict()
                    put_field_data['container']['resources'][metric]["max"] = int(cont['{0}_max'.format(metric)])
                    put_field_data['container']['resources'][metric]["current"] = int(cont['{0}_min'.format(metric)])
                    put_field_data['container']['resources'][metric]["min"] = int(cont['{0}_min'.format(metric)])
                    put_field_data['container']['resources'][metric]["guard"] = True
                    if '{0}_weight'.format(metric) in cont: put_field_data['container']['resources'][metric]["weight"] = int(cont['{0}_weight'.format(metric)])

            ## Limits
            for res in cont_resources:
                put_field_data['limits']["resources"][res] = {}
                if cont[f'{res}_boundary'] == 0:
                    put_field_data['limits']["resources"][res]["boundary"] = int(config[f'{res}_boundary'])
                    put_field_data['limits']["resources"][res]["boundary_type"] = str(cont[f'{res}_boundary_type'])
                else:
                    put_field_data['limits']["resources"][res]["boundary"] = int(cont[f'{res}_boundary'])
                    put_field_data['limits']["resources"][res]["boundary_type"] = str(cont[f'{res}_boundary_type'])

            error_message = "Error adding container {0} | Data: {1}".format(cont['container_name'], put_field_data)
            error, response = request_to_state_db(full_url, "put", error_message, put_field_data, session=session)

            if response != "" and error:
                if response.status_code == 400 and "already exists" in error: print("Container {0} already exists".format(cont['container_name']))
                else: raise Exception(error)
