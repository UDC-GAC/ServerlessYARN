# /usr/bin/python
import sys
import yaml
import requests
import json
from bs4 import BeautifulSoup

bandwidth_conversion = {}
bandwidth_conversion["B/s"] =  0.00000095367432
bandwidth_conversion["KB/s"] = 0.0009765625
bandwidth_conversion["MB/s"] = 1
bandwidth_conversion["GB/s"] = 1024
bandwidth_conversion["TB/s"] = 1048576

# usage example: update_host_disks_bw.py host0 ssd_0 100 MB/s config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 5):
        host = sys.argv[1]
        disk = sys.argv[2]
        bandwidth = float(sys.argv[3])
        unit = sys.argv[4]
        with open(sys.argv[5], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        orchestrator_url = "http://{0}:{1}".format(config['server_ip'],config['orchestrator_port'])
        headers = {'Content-Type': 'application/json'}

        session = requests.Session()

        ## Update host
        full_url = "{0}/structure/host/{1}/disks".format(orchestrator_url, host)

        bandwidth_MB = round(bandwidth * bandwidth_conversion[unit])

        put_field_data = {}
        put_field_data['resources'] = {}
        put_field_data['resources']['disks'] = []
        put_field_data['resources']['disks'].append({'name':disk, 'max': bandwidth_MB})

        r = session.post(full_url, data=json.dumps(put_field_data), headers=headers)

        if (r != "" and r.status_code != requests.codes.ok):
            soup = BeautifulSoup(r.text, features="html.parser")
            raise Exception("Error updating host '{0}' disk information: {1}".format(host, soup.get_text().strip()))
