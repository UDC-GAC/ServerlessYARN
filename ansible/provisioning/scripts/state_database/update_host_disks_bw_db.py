#!/usr/bin/python
import sys
import yaml
import requests
from serverlessyarn_utils.web_utils import web_request

bandwidth_conversion = {}
bandwidth_conversion["B/s"] =  0.00000095367432
bandwidth_conversion["KB/s"] = 0.0009765625
bandwidth_conversion["MB/s"] = 1
bandwidth_conversion["GB/s"] = 1024
bandwidth_conversion["TB/s"] = 1048576

# usage example: update_host_disks_bw_db.py host0 ssd_0 500 100 MB/s config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 6):
        host = sys.argv[1]
        disk = sys.argv[2]
        read_bandwidth = float(sys.argv[3])
        write_bandwidth = float(sys.argv[4])
        unit = sys.argv[5]
        with open(sys.argv[6], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        orchestrator_url = "http://{0}:{1}".format(config['server_ip'],config['orchestrator_port'])

        session = requests.Session()

        ## Update host
        full_url = "{0}/structure/host/{1}/disks".format(orchestrator_url, host)

        read_bandwidth_MB = round(read_bandwidth * bandwidth_conversion[unit])
        write_bandwidth_MB = round(write_bandwidth * bandwidth_conversion[unit])

        put_field_data = {}
        put_field_data['resources'] = {}
        put_field_data['resources']['disks'] = []
        put_field_data['resources']['disks'].append({'name':disk, 'max_read': read_bandwidth_MB, 'max_write': write_bandwidth_MB})

        error_message = "Error updating host '{0}' disk information".format(host)
        error, _ = web_request(full_url, "post", error_message, put_field_data, session=session)

        if error: raise Exception(error)
