# /usr/bin/python
import sys
import yaml
import requests
import json
from bs4 import BeautifulSoup

rescaler_port = "8000"
cpu_default_boundary = 20
mem_default_boundary = 256

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
        resources = dict(
            cpu = dict(),
            mem = dict()
        )
    )
)

base_host_to_API = dict(
    name = "base_host",
    host = "base_host",
    subtype = "host",
    host_rescaler_ip = "base_host",
    host_rescaler_port = rescaler_port,
    resources = dict(
        cpu = dict(),
        mem = dict()
    )
)

# usage example: add_containers.py host0 4 4096 cont0,cont1 200 100 50 2048 1024 512 config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 11):
        new_host = sys.argv[1]
        host_cpu = int(sys.argv[2])
        host_mem = int(sys.argv[3])
        containers = sys.argv[4].split(',')
        max_cpu_percentage_per_container = int(sys.argv[5])
        min_cpu_percentage_per_container = int(sys.argv[6])
        cpu_boundary = int(sys.argv[7])
        if cpu_boundary == 0: cpu_boundary = cpu_default_boundary
        max_memory_per_container = int(sys.argv[8])
        min_memory_per_container = int(sys.argv[9])
        mem_boundary = int(sys.argv[10])
        if mem_boundary == 0: mem_boundary = mem_default_boundary
        with open(sys.argv[11], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        host_shares = host_cpu * 100
        orchestrator_url = "http://{0}:{1}".format(config['server_ip'],config['orchestrator_port'])
        headers = {'Content-Type': 'application/json'}

        ## Add host
        full_url = "{0}/structure/host/{1}".format(orchestrator_url, new_host)

        put_field_data = base_host_to_API
        put_field_data['name'] = new_host
        put_field_data['host'] = new_host
        put_field_data['host_rescaler_ip'] = new_host

        put_field_data['resources']["cpu"]["max"] = host_shares
        put_field_data['resources']["cpu"]["free"] = host_shares

        put_field_data['resources']["mem"]["max"] = host_mem
        put_field_data['resources']["mem"]["free"] = host_mem

        r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

        if (r != "" and r.status_code != requests.codes.ok):
            soup = BeautifulSoup(r.text, features="html.parser")
            if r.status_code == 400 and "already exists" in soup.get_text().strip():
                # Host already exists
                print("Host {0} already exists".format(new_host))
            else:
                raise Exception("Error adding host {0}: {1}".format(new_host, soup.get_text().strip()))

        ## Add containers
        for cont in containers:
            full_url = "{0}/structure/container/{1}".format(orchestrator_url, cont)

            put_field_data = base_container_to_API
            ## Container info
            put_field_data['container']["name"] = cont
            put_field_data['container']['host_rescaler_ip'] = new_host
            put_field_data['container']['host'] = new_host

            put_field_data['container']['resources']["cpu"]["max"] = max_cpu_percentage_per_container
            put_field_data['container']['resources']["cpu"]["current"] = max_cpu_percentage_per_container
            put_field_data['container']['resources']["cpu"]["min"] = min_cpu_percentage_per_container
            put_field_data['container']['resources']["cpu"]["guard"] = True

            put_field_data['container']['resources']["mem"]["max"] = max_memory_per_container
            put_field_data['container']['resources']["mem"]["current"] = max_memory_per_container
            put_field_data['container']['resources']["mem"]["min"] = min_memory_per_container
            put_field_data['container']['resources']["mem"]["guard"] = True

            ## Limits
            put_field_data['limits']["resources"]["cpu"]["boundary"] = cpu_boundary
            put_field_data['limits']["resources"]["mem"]["boundary"] = mem_boundary

            r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

            if (r != "" and r.status_code != requests.codes.ok):
                soup = BeautifulSoup(r.text, features="html.parser")
                if r.status_code == 400 and "already exists" in soup.get_text().strip():
                    # Container already exists
                    print("Container {0} already exists".format(cont))
                else:
                    raise Exception("Error adding container {0}: {1}".format(cont, soup.get_text().strip()))