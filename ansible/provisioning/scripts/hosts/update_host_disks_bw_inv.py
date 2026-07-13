#!/usr/bin/python
import sys
import yaml
from serverlessyarn_utils.manage_inventory import AnsibleYamlInventory

rescaler_port = "8000"

bandwidth_conversion = {}
bandwidth_conversion["B/s"] =  0.00000095367432
bandwidth_conversion["KB/s"] = 0.0009765625
bandwidth_conversion["MB/s"] = 1
bandwidth_conversion["GB/s"] = 1024
bandwidth_conversion["TB/s"] = 1048576

# usage example: update_host_disks_bw_inv.py host0 ssd_0 500 100 MB/s config/config.yml

if __name__ == "__main__":

    if (len(sys.argv) > 6):
        host = sys.argv[1]
        disk = sys.argv[2]
        read_bandwidth = float(sys.argv[3])
        write_bandwidth = float(sys.argv[4])
        unit = sys.argv[5]
        with open(sys.argv[6], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        read_bandwidth_MB = round(read_bandwidth * bandwidth_conversion[unit])
        write_bandwidth_MB = round(write_bandwidth * bandwidth_conversion[unit])

        inventory = AnsibleYamlInventory()
        inventory.update_disk(hostname=host, disk=disk, new_disk_info={"read_bw": read_bandwidth_MB, "write_bw": write_bandwidth_MB})
        inventory.save()