import json
import requests
import sys

# usage example: init_host_node_rescaler.py host0 cpu 4 cont0,cont1

node_recaler_port = 8000

if __name__ == "__main__":
    
    host = sys.argv[1]
    resource = sys.argv[2]
    resource_max_value = int(sys.argv[3])
    containers = sys.argv[4].split(',')

    base_url = "http://" + host + ":" + str(node_recaler_port) + "/container/"
    headers = {'Content-Type': 'application/json'}

    if (resource == "cpu"):
        # cpu_allowance_limit
        max_cores = resource_max_value
        cpu_allowance_limit = max_cores / len(containers) * 100
        total_allowance_allocated = 0

    elif (resource == "mem"):
        # mem_limit
        max_memory = resource_max_value
        mem_limit = max_memory / len(containers)
        put_field_data = {"mem": {"mem_limit": mem_limit, "unit": "M"}}


    for c in containers:
        full_url = base_url + c

        r = requests.get(full_url)   
        requested_data = json.loads(r.content)

        ## initialize only if not initialized previously
        not_initialized = False

        if (resource == "cpu"):

            # cpu_num
            initial_core = int(total_allowance_allocated // 100)
            total_allowance_allocated += cpu_allowance_limit
            last_core = int((total_allowance_allocated - 1) // 100)
            if (last_core > initial_core):
                cpu_num = str(initial_core) + "-" + str(last_core)
            else:
                 cpu_num = str(initial_core)

            put_field_data = {"cpu": {"cpu_allowance_limit": cpu_allowance_limit,"cpu_num": cpu_num}}

            not_initialized = int(requested_data['cpu']['cpu_allowance_limit']) == -1

        elif (resource == "mem"):

            not_initialized = int(requested_data['mem']['mem_limit']) == -1 

        if (not_initialized):

            r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

            if (r.status_code == requests.codes.ok):
                print("Container " + c + " updated with: " + str(put_field_data))
            else:
                print("Error initializing " + resource + " value for " + c + " in host " + host)


