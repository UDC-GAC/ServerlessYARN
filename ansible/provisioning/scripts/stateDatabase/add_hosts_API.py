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
    resources = dict(
        cpu = dict(),
        mem = dict(),
        disks = []
    )
)

# usage example: add_hosts_API.py host0 4 4096 {'ssd_0':'$HOME/ssd','hdd_0':'$HOME/hdd'} config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 5):
        new_host = sys.argv[1]
        host_cpu = int(sys.argv[2])
        host_mem = int(sys.argv[3])
        disks = json.loads(sys.argv[4].replace('\'','"'))
        with open(sys.argv[5], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        host_shares = host_cpu * 100
        orchestrator_url = "http://{0}:{1}".format(config['server_ip'],config['orchestrator_port'])
        headers = {'Content-Type': 'application/json'}

        session = requests.Session()

        ## Add host
        full_url = "{0}/structure/host/{1}".format(orchestrator_url, new_host)

        put_field_data = base_host_to_API
        put_field_data['name'] = new_host
        put_field_data['host'] = new_host
        put_field_data['host_rescaler_ip'] = new_host

        put_field_data['resources']["cpu"]["max"] = int(host_shares)
        put_field_data['resources']["cpu"]["free"] = int(host_shares)

        put_field_data['resources']["mem"]["max"] = int(host_mem)
        put_field_data['resources']["mem"]["free"] = int(host_mem)

        create_lvm = config['create_lvm']

        for disk in disks:
            if not create_lvm or "lvm" in disk:
                new_disk = {}
                new_disk['name'] = disk
                new_disk['path'] = disks[disk]
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
