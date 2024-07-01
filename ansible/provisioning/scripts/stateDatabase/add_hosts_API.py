# /usr/bin/python
import sys
import yaml
import requests
import json
from bs4 import BeautifulSoup

rescaler_port = "8000"

base_host_to_API = dict(
    name = "base_host",
    host = "base_host",
    subtype = "host",
    host_rescaler_ip = "base_host",
    host_rescaler_port = rescaler_port,
    resources = dict()
)

# usage example: add_hosts_API.py host0 {'cpu': 4, 'mem': 4096, 'energy': 200} {'ssd_0':{'path':'$HOME/ssd','bw':500},'hdd_0':{'path':'$HOME/hdd','bw':100}} config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 4):
        new_host = sys.argv[1]
        host_resources = json.loads(sys.argv[2].replace('\'', '"'))
        disks = json.loads(sys.argv[3].replace('\'', '"'))
        with open(sys.argv[4], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        orchestrator_url = "http://{0}:{1}".format(config['server_ip'],config['orchestrator_port'])
        headers = {'Content-Type': 'application/json'}

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

        put_field_data['resources']["disks"] = []
        for disk in disks:
            if not create_lvm or "lvm" in disk:
                new_disk = {}
                new_disk['name'] = disk
                new_disk['path'] = disks[disk]['path']
                new_disk['max']  = disks[disk]['bw']
                new_disk['free'] = disks[disk]['bw']
                new_disk['load'] = 0
                if   "ssd" in disk: new_disk['type'] = "SSD"
                elif "hdd" in disk: new_disk['type'] = "HDD"
                elif "lvm" in disk: new_disk['type'] = "LVM"
                else: raise Exception("Disk {0} has an invalid type".format(disk))
                put_field_data['resources']["disks"].append(new_disk)

        r = session.put(full_url, data=json.dumps(put_field_data), headers=headers)

        if (r != "" and r.status_code != requests.codes.ok):
            soup = BeautifulSoup(r.text, features="html.parser")
            if r.status_code == 400 and "already exists" in soup.get_text().strip():
                # Host already exists
                print("Host {0} already exists".format(new_host))
            else:
                raise Exception("Error adding host {0}: {1}".format(new_host, soup.get_text().strip()))
