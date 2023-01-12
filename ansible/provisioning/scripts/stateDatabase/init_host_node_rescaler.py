# /usr/bin/python
import json
import requests
import sys
import yaml
import itertools
import src.StateDatabase.couchdb as couchDB

# usage example: init_host_node_rescaler.py host0 cpu 4 cont0,cont1 config/config.yml

node_recaler_port = 8000


def getIntegerListRange(list_num):

    groups = (list(x) for _, x in itertools.groupby(list_num, lambda x, c=itertools.count(): x - next(c)))
    num_range = ','.join('-'.join(map(str, (item[0], item[-1])[:len(item)])) for item in groups)
    return num_range

if __name__ == "__main__":
    
    handler = couchDB.CouchDBServer()
    database = "structures"

    host = sys.argv[1]
    resource = sys.argv[2]
    resource_max_value = int(sys.argv[3])
    containers = sys.argv[4].split(',')
    with open(sys.argv[5], "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    base_url = "http://" + host + ":" + str(node_recaler_port) + "/container/"
    headers = {'Content-Type': 'application/json'}

    new_containers = containers
    host_found = False
    if handler.database_exists(database):
        try:
            host_info = handler.get_structure(host)
            host_found = True

            new_containers = []
            for cont in containers:
                try:
                    cont_info = handler.get_structure(cont)
                except ValueError:
                    # new container
                    new_containers.append(cont)

        except ValueError:
            # host does not exist
            pass

    if (resource == "cpu"):
        # cpu_allowance_limit
        if host_found and resource in host_info['resources']:
            free_cpu = host_info['resources'][resource]['free']
        else:
            max_cores = resource_max_value
            free_cpu = max_cores * 100

        if len(new_containers) > 0:
            max_cpu_division = int(free_cpu / len(new_containers))
        else:
            max_cpu_division = 0
        max_cpu_percentage_per_container = int(config['max_cpu_percentage_per_container'])
        cpu_allowance_limit = min(max_cpu_division, max_cpu_percentage_per_container)
        total_allowance_allocated = 0
        current_core = 0

    elif (resource == "mem"):
        # mem_limit
        if host_found and resource in host_info['resources']:
            free_memory = host_info['resources'][resource]['free']
        else:
            free_memory = resource_max_value

        if len(new_containers) > 0:
            max_mem_division = free_memory / len(new_containers)
        else:
            max_mem_division = 0
        max_memory_per_container = int(config['max_memory_per_container'])
        mem_limit = min(max_mem_division, max_memory_per_container)

    for c in containers:
        full_url = base_url + c

        r = requests.get(full_url)   
        requested_data = json.loads(r.content)

        ## initialize only if not initialized previously
        not_initialized = False

        if (resource == "cpu"):

            not_initialized = int(requested_data['cpu']['cpu_allowance_limit']) == -1

            # Host already stored in StateDatabase
            if host_found and resource in host_info['resources'] and "core_usage_mapping" in host_info['resources'][resource]:

                if not_initialized:
                    if c in new_containers:
                        # Container not added to the StateDatabase yet
                        to_allocate = cpu_allowance_limit
                        cont_cpu_allowance_limit = cpu_allowance_limit
                else:
                    continue

                core_mapping = host_info['resources'][resource]['core_usage_mapping']
                number_of_cores = len(core_mapping)
                current_free = core_mapping[str(current_core)]['free']

                cpu_core_list = []

                if c in new_containers:
                    while (to_allocate > 0 and current_core < number_of_cores):
                        if (to_allocate >= 100):
                            if current_free > 0: cpu_core_list.append(current_core)
                            core_mapping[str(current_core)][c] = current_free
                            core_mapping[str(current_core)]["free"] -= current_free
                            to_allocate -= current_free
                            current_core += 1
                            if current_core < number_of_cores: current_free = core_mapping[str(current_core)]['free']

                        else:
                            if current_free > 0: cpu_core_list.append(current_core)
                            min_usage = min(current_free, to_allocate)
                            core_mapping[str(current_core)][c] = min_usage
                            core_mapping[str(current_core)]["free"] -= min_usage
                            if (min_usage == to_allocate):
                                ## we continue in current core
                                current_free -= to_allocate
                                to_allocate = 0
                            else:
                                ## we switch to next core
                                to_allocate -= current_free
                                current_core += 1
                                if current_core < number_of_cores: current_free = core_mapping[str(current_core)]['free']

                else:
                    allocated = 0
                    for core in range(0,number_of_cores):
                        if c in core_mapping[str(core)]:
                            allocated += core_mapping[str(core)][c]
                            cpu_core_list.append(core)

                    cont_cpu_allowance_limit = allocated

                cpu_num = getIntegerListRange(cpu_core_list)

            # Host not in StateDatabase yet
            else:
                cont_cpu_allowance_limit = cpu_allowance_limit

                # cpu_num
                initial_core = int(total_allowance_allocated // 100)
                total_allowance_allocated += cont_cpu_allowance_limit
                last_core = int((total_allowance_allocated - 1) // 100)
                if (last_core > initial_core):
                    cpu_num = str(initial_core) + "-" + str(last_core)
                else:
                    cpu_num = str(initial_core)

            put_field_data = {"cpu": {"cpu_allowance_limit": cont_cpu_allowance_limit,"cpu_num": cpu_num}}

        elif (resource == "mem"):

            not_initialized = int(requested_data['mem']['mem_limit']) == -1 

            if not_initialized:
                if c in new_containers:
                    cont_mem_limit = mem_limit
                else:
                    # Container already added to the StateDatabase (but not initialized)
                    cont_info = handler.get_structure(c)
                    cont_mem_limit = cont_info['resources']['mem']['current']
                    if cont_mem_limit == -1: cont_mem_limit = cont_info['resources']['mem']['max']
            else:
                continue

            put_field_data = {"mem": {"mem_limit": cont_mem_limit, "unit": "M"}}

        if (not_initialized):

            r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

            if (r.status_code == requests.codes.ok):
                print("Container " + c + " updated with: " + str(put_field_data))
            else:
                # For some reason, the first initialization always results in an error, but it actually works
                print("Response from node scaler: " + str(r.content))
                print("Error initializing " + resource + " value for " + c + " in host " + host)
