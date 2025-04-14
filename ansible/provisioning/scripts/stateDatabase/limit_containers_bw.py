# /usr/bin/python
import sys
import yaml
import requests
import json
from bs4 import BeautifulSoup
import time
import src.StateDatabase.couchdb as couchDB
from src.MyUtils.MyUtils import generate_request

cap_bw = 0.15 # 20% of max bw

# usage example: limit_containers_bw.py host0,host1 config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 2):
        hosts = sys.argv[1].split(',')
        with open(sys.argv[2], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        orchestrator_url = "http://{0}:{1}".format(config['server_ip'],config['orchestrator_port'])
        headers = {'Content-Type': 'application/json'}

        session = requests.Session()

        couchdb_handler = couchDB.CouchDBServer()

        ## Get all structures
        structures_url = "{0}/structure/".format(orchestrator_url)
        response = session.get(structures_url)
        requested_data = json.loads(response.content)

        host_list = {}
        for structure in requested_data:
            if structure['subtype'] == 'host' and structure['name'] in hosts:
                host_list[structure['name']] = structure
                host_list[structure['name']]['containers'] = []

        for structure in requested_data:
            if structure['subtype'] == 'container' and structure['host'] in host_list:
                host_list[structure['host']]['containers'].append(structure)

        final_requests = list()

        for host in host_list:
            host_info = host_list[host]
            max_write = host_info['resources']['disks']['lvm']['max']

            host_limited_write = (max_write) * cap_bw

            if len(host_info['containers']) > 0:
                containers_limited_write = host_limited_write / len(host_info['containers'])

            for container in host_info['containers']:
                write_to_escale = max(containers_limited_write, container['resources']['disk']['min']) - container['resources']['disk']['current']

                if write_to_escale < 0:
                    request = generate_request(container, write_to_escale, "disk")
                    final_requests.append(request)

        ## TODO: get scaler timelapse from service config
        SCALER_TIMELAPSE = 5
        time.sleep(SCALER_TIMELAPSE) # wait SCALER TIMELAPSE to avoid mixing this requests with older requests from other services

        print("FINAL REQUESTS ARE:")
        for r in final_requests:
            print(r)
            couchdb_handler.add_request(r)