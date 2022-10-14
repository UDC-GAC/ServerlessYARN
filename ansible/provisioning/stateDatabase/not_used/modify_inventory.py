#!/usr/bin/env python
import sys
import io

# usage example: modify_inventory.py /etc/ansible/hosts host0 cont0,cont1

inventory_file = sys.argv[1]
host = sys.argv[2]
containers = sys.argv[3]

## format container list from cont0,cont1 to \'["cont0","cont1"]\'
container_list = containers.split(',')

i = 0
containers_formatted = "\'["

while (i < len(container_list) - 1):
    containers_formatted += "\"" + container_list[i] + "\","
    i += 1
    
containers_formatted += "\"" + container_list[i] + "\"]\'"

# read lines
with open(inventory_file, 'r') as file:
    # read a list of lines into data
    data = file.readlines()


i = 0

# skip to nodes
while (i < len(data) and data[i] != "[nodes]\n"):
    i+=1

i+=1

# skip to desired node
while (i < len(data) and host not in data[i]):
    i+=1

if (i < len(data)):
    data[i] = host + " containers=" + containers_formatted + "\n"
    with open(inventory_file, 'w') as file:
        file.writelines( data )

