#!/usr/bin/python
import sys
import yaml
import requests
import json
from serverlessyarn_utils.web_utils import web_request

rescaler_port = "8000"

allocate_current_as_min = False ## False to allow ServerlessContainers to set the initial allocation considering boundaries

# usage example: add_containers.py [{'container_name': 'host1-cont1', 'host': 'host1', 'cpu_max': 200, 'cpu_min': 50, 'mem_max': 2048, 'mem_min': 1024, 'energy_max': 100, 'energy_min': 30, 'cpu_boundary': 25, 'mem_boundary': 256, 'energy_boundary': 10, 'disk': 'hdd_0', 'disk_path: '$HOME/hdd', 'disk_max': 200, 'disk_min': 50}, {'container_name': 'host1-cont1'...}] config/config.yml

def create_container_info(container_data, resources, config):

    container_info = dict(
        container = dict(
            name = container_data['container_name'],
            resources = dict(),
            host_rescaler_ip = container_data['host'],
            host_rescaler_port = rescaler_port,
            host = container_data['host'],
            guard = (container_data.get('guard', 'true') == 'true'),
            subtype = 'container'
        ),
        limits = dict(
            resources = dict()
        )
    )

    for res in resources:
        ## Resources
        container_info['container']['resources'][res] = dict()
        container_info['container']['resources'][res]['max'] = int(container_data[f'{res}_max'])
        container_info['container']['resources'][res]['min'] = int(container_data[f'{res}_min'])
        container_info['container']['resources'][res]['guard'] = (container_data.get(f'{res}_guard', 'true') == 'true')
        if f'{res}_weight' in container_data:
            container_info['container']['resources'][res]['weight'] = float(container_data[f'{res}_weight'])
        if allocate_current_as_min:
            container_info['container']['resources'][res]['current'] = int(container_data[f'{res}_min'])
        else:
            container_info['container']['resources'][res]['current'] = -1 ## use -1 as a signal for ServerlessContainers

        ## Limits
        container_info['limits']['resources'][res] = dict()
        if container_data[f'{res}_boundary'] == 0:
            container_info['limits']['resources'][res]['boundary'] = int(config[f'{res}_boundary'])
            container_info['limits']['resources'][res]['boundary_type'] = str(container_data[f'{res}_boundary_type'])
        else:
            container_info['limits']['resources'][res]['boundary'] = int(container_data[f'{res}_boundary'])
            container_info['limits']['resources'][res]['boundary_type'] = str(container_data[f'{res}_boundary_type'])

    ## Specific disk info
    if 'disk_read' in resources and 'disk_write' in resources:
        container_info['container']['resources']['disk'] = dict()
        container_info['container']['resources']['disk']['name'] = container_data['disk']
        container_info['container']['resources']['disk']['path'] = container_data['disk_path']

    return container_info

def subscribe_containers_to_app(url, app_name, app_containers):

    def add_container_to_app_in_db(full_url, container_name, app_name):
        max_retries = 10
        actual_try = 0

        while actual_try < max_retries:

            error_message = "Error adding container {0} to app {1}".format(container_name, app_name)
            error, response = web_request(full_url, "put", error_message)

            if response != "":
                if not error: break
                elif response.status_code == 400 and "already subscribed" in error: break # Container is already subscribed
                else: raise Exception(error)

            actual_try += 1

        if actual_try >= max_retries:
            raise Exception("Reached max tries when adding {0} to app {1}".format(container_name, app_name))

    # Subscribe containers to app in ServerlessContainers database
    for container in app_containers:
        full_url = url + "container/{0}/{1}".format(container['container_name'], app_name)
        add_container_to_app_in_db(full_url, container['container_name'], app_name)

if __name__ == "__main__":

    if (len(sys.argv) > 2):
        containers = json.loads(sys.argv[1].replace('\'','"'))
        with open(sys.argv[2], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        orchestrator_url = "http://{0}:{1}".format(config['server_ip'], config['orchestrator_port'])
        session = requests.Session()

        ## Check if an app has been passed as argument to add the containers to it
        app_name = None
        if len(sys.argv) == 4:
            app_name = sys.argv[3]

        ## Add containers
        for cont in containers:

            full_url = "{0}/structure/container/{1}".format(orchestrator_url, cont['container_name'])

            ## Resources to manage
            cont_resources = ["cpu", "mem"]
            if 'power_budgeting' in config and config['power_budgeting']:
                cont_resources.append("energy")
            if 'disk' in cont and config['disk_capabilities'] and config['disk_scaling']:
                cont_resources.append("disk_read")
                cont_resources.append("disk_write")

            put_field_data = create_container_info(cont, cont_resources, config)
            error_message = "Error adding container {0} | Data: {1}".format(cont['container_name'], put_field_data)
            error, response = web_request(full_url, "put", error_message, put_field_data, session=session)

            if response != "" and error:
                if response.status_code == 400 and "already exists" in error: print("Container {0} already exists".format(cont['container_name']))
                else: raise Exception(error)

        ## Add containers to the app
        if app_name: subscribe_containers_to_app(
            url="{0}/structure/".format(orchestrator_url),
            app_name=app_name,
            app_containers=containers
        )
