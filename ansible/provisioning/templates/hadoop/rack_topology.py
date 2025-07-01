#!/usr/bin/python3

import ipaddress
import sys
from math import log

sys.argv.pop(0) # discard name of topology script from argv list as we just want IP addresses

subnet = ipaddress.ip_network("{{ subnet }}")
number_of_hosts = {{ groups['nodes'] | length }}

number_of_subnets = 1<<(number_of_hosts-1).bit_length()
subnets = list(subnet.subnets(prefixlen_diff=int(log(number_of_subnets,2))))

for ip in sys.argv:
    address = ipaddress.ip_address(ip)
    subnet_found = False
    count = 0
    for net in subnets:
        if address in net:
            subnet_found = True 
            #print("/{0}".format(net[0]))
            print("/rack-{0}".format(str(count).zfill(2)))
            break
        count += 1
    if not subnet_found: print("/rack-unknown")
