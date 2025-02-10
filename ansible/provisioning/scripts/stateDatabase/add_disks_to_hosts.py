# /usr/bin/python
import sys
import yaml
import requests
import json
import os

# usage example: add_disks_to_hosts.py {"host0":{"new_0":{"path":"$HOME/new_0"}}} config/config.yml

from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager

scriptDir = os.path.realpath(os.path.dirname(__file__))
inventory_file = scriptDir + "/../../../ansible.inventory"

sys.path.append(scriptDir + "/../../services/serverless_containers_web/ui")
from utils import request_to_state_db

if __name__ == "__main__":

    if (len(sys.argv) > 2):
        new_disks = json.loads(sys.argv[1].replace('\'','"'))
        with open(sys.argv[2], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        orchestrator_url = "http://{0}:{1}".format(config['server_ip'],config['orchestrator_port'])

        session = requests.Session()

        ## Load ansible inventory to get disks BW
        loader = DataLoader()
        ansible_inventory = InventoryManager(loader=loader, sources=inventory_file)
        hostList = ansible_inventory.groups['nodes'].get_hosts()

        ## Update hosts
        for h in hostList:

            if h.name not in new_disks: continue

            host = h.name
            disks = h.vars['disks']

            full_url = "{0}/structure/host/{1}/disks".format(orchestrator_url, host)

            put_field_data = {}
            put_field_data['resources'] = {}
            put_field_data['resources']['disks'] = []

            for disk in disks:

                if disk not in new_disks[host]: continue

                new_disk = {}
                new_disk['name'] = disk
                new_disk['path'] = disks[disk]['path']
                new_disk['max']  = disks[disk]['bw']
                new_disk['free'] = disks[disk]['bw']
                new_disk['load'] = 0

                ## TODO: eventually remove the 'type' attribute, since we can differentiate disks by their bandwidth
                if   "ssd" in disk: new_disk['type'] = "SSD"
                elif "hdd" in disk: new_disk['type'] = "HDD"
                elif "lvm" in disk: new_disk['type'] = "LVM"
                elif "new" in disk: new_disk['type'] = "SSD"
                else: raise Exception("Disk {0} has an invalid type".format(disk))

                put_field_data['resources']["disks"].append(new_disk)

            error_message = "Error adding disks {0} to host '{1}'".format(new_disk[host], host)
            error, _ = request_to_state_db(full_url, "put", error_message, put_field_data, session=session)

            if error: raise Exception(error)
