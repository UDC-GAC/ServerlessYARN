# /usr/bin/python
import sys
import yaml
import requests
import json
import os

rescaler_port = "8000"

base_host_to_API = dict(
    name = "base_host",
    host = "base_host",
    subtype = "host",
    host_rescaler_ip = "base_host",
    host_rescaler_port = rescaler_port,
    resources = dict()
)

scriptDir = os.path.realpath(os.path.dirname(__file__))
sys.path.append(scriptDir + "/../../services/serverless_containers_web/ui")
from utils import request_to_state_db

# usage example: add_hosts_API.py host0 {'cpu': 4, 'mem': 4096, 'energy': 200} {'ssd_0':{'path':'$HOME/ssd','read_bw':500,'write_bw':400},'hdd_0':{'path':'$HOME/hdd','read_bw':150,'write_bw':100}} config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 4):
        new_host = sys.argv[1]
        host_resources = json.loads(sys.argv[2].replace('\'', '"'))
        if sys.argv[3] != "None":
            disks = json.loads(sys.argv[3].replace('\'', '"'))
        else:
            disks = None
        with open(sys.argv[4], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        orchestrator_url = "http://{0}:{1}".format(config['server_ip'],config['orchestrator_port'])

        session = requests.Session()

        ## Add host
        full_url = "{0}/structure/host/{1}".format(orchestrator_url, new_host)

        put_field_data = base_host_to_API
        put_field_data['name'] = new_host
        put_field_data['host'] = new_host
        put_field_data['host_rescaler_ip'] = new_host

        for resource in host_resources:
            value = int(host_resources[resource])
            if value is None:  # Value doesn't exist in ansible inventory, ignoring
                continue
            if resource == 'cpu':
                value *= 100  # 100 shares per CPU
            put_field_data['resources'][resource] = dict()
            put_field_data['resources'][resource]["max"] = value
            put_field_data['resources'][resource]["free"] = value

        create_lvm = config['create_lvm']

        if disks:
            put_field_data['resources']["disks"] = []
            for disk in disks:
                if not create_lvm or "lvm" in disk:
                    new_disk = {}
                    new_disk['name'] = disk
                    new_disk['path'] = disks[disk]['path']
                    new_disk['max_read']  = disks[disk]['read_bw']
                    new_disk['free_read'] = disks[disk]['read_bw']
                    new_disk['max_write']  = disks[disk]['write_bw']
                    new_disk['free_write'] = disks[disk]['write_bw']
                    new_disk['load'] = 0
                    if   "ssd" in disk: new_disk['type'] = "SSD"
                    elif "hdd" in disk: new_disk['type'] = "HDD"
                    elif "lvm" in disk: new_disk['type'] = "LVM"
                    else: raise Exception("Disk {0} has an invalid type".format(disk))
                    put_field_data['resources']["disks"].append(new_disk)

        error_message = "Error adding host {0}".format(new_host)
        error, response = request_to_state_db(full_url, "put", error_message, put_field_data, session=session)

        if response != "" and error:
            if response.status_code == 400 and "already exists" in error: print("Host {0} already exists".format(new_host))
            else: raise Exception(error)
