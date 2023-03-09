#!/usr/bin/python
import sys
import ipaddress
from math import sqrt

# usage example: get_subnets.py 10.22.0.0/16 host0,host1,host2 192.168.56.100,192.168.56.102,192.168.56.103

if __name__ == "__main__":

    if (len(sys.argv) > 3):
        subnet = ipaddress.ip_network(sys.argv[1])

        # hosts and iface_ip_list must have same length
        hosts = sys.argv[2].split(',')
        iface_ip_list = sys.argv[3].split(',')

        number_of_subnets = 1<<(len(hosts)-1).bit_length()
        subnets = list(subnet.subnets(prefixlen_diff=int(sqrt(number_of_subnets))))

        host_dict = {}

        for i in range(0, len(hosts)):
            host_dict[hosts[i]] = {}
            host_dict[hosts[i]]['iface_ip'] = str(iface_ip_list[i])
            host_dict[hosts[i]]['subnet'] = str(subnets[i])
            host_dict[hosts[i]]['rangeStart'] = str(subnets[i][1])
            host_dict[hosts[i]]['rangeEnd'] = str(subnets[i][-2])

        print(host_dict)
