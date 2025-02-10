# /usr/bin/python
import json
import requests
import sys
import itertools
import time
import src.StateDatabase.couchdb as couchDB
import os

scriptDir = os.path.realpath(os.path.dirname(__file__))
sys.path.append(scriptDir + "/../../services/serverless_containers_web/ui")
from utils import request_to_state_db

# usage example: init_host_node_rescaler_v3.py host1 [{'container_name': 'host1-cont0', 'host': 'host1', 'cpu_max': 200, 'cpu_min': 50, 'mem_max': 2048, 'mem_min': 1024, 'disk': 'ssd_0', 'disk_path': '$HOME/ssd', 'disk_max': 200, 'disk_min': 50, 'energy_max': 100, 'energy_min': 30}, {'container_name': 'host1-cont1'...}] ['cpu','mem','disk','energy']

NODE_RESCALER_PORT = 8000
COUCHDB_INIT_TRIES = 10
COUCHDB_INIT_WAIT = 0.5


def get_integer_list_range(list_num):

    groups = (list(x) for _, x in itertools.groupby(list_num, lambda x, c=itertools.count(): x - next(c)))
    num_range = ','.join('-'.join(map(str, (item[0], item[-1])[:len(item)])) for item in groups)
    return num_range


if __name__ == "__main__":

    handler = couchDB.CouchDBServer()
    database = "structures"

    if len(sys.argv) > 3:
        host = sys.argv[1]
        containers = json.loads(sys.argv[2].replace('\'', '"'))
        resources = json.loads(sys.argv[3].replace('\'', '"'))

        base_url = "http://{0}:{1}/container/".format(host, str(NODE_RESCALER_PORT))

        # No containers requested
        if len(containers) == 0:
            sys.exit(0)

        new_containers = containers
        host_found = False
        host_info = None

        # Wait for couchdb to be up a minimum of 5s
        couchdb_up = False
        tries = 0
        while not couchdb_up and tries < COUCHDB_INIT_TRIES:
            try:
                couchdb_up = handler.database_exists(database)
            except Exception:
                couchdb_up = False
            finally:
                tries += 1
                time.sleep(COUCHDB_INIT_WAIT)
                print("StateDatabase is {0}".format("up" if couchdb_up else "down. Retrying..."))

        if handler.database_exists(database):
            try:
                host_info = handler.get_structure(host)
                host_found = True
                new_containers = []
                for cont in containers:
                    try:
                        cont_info = handler.get_structure(cont['container_name'])
                    except ValueError:  # Container not found (new container)
                        new_containers.append(cont)
            except ValueError:
                # host does not exist
                pass

        for c in containers:
            if host != c['host']:
                continue
            full_url = base_url + c['container_name']
            r = requests.get(full_url)
            requested_data = json.loads(r.content)
            put_field_data = {}

            # Initialize only if not initialized previously
            not_initialized = False
            not_initialized_resources = 0

            if "cpu" in resources:
                total_allowance_allocated = 0
                current_core = 0
                not_initialized = int(requested_data['cpu']['cpu_allowance_limit']) == -1
                if not_initialized:
                    not_initialized_resources += 1

                # Host already stored in StateDatabase
                if host_found and "cpu" in host_info['resources'] and "core_usage_mapping" in host_info['resources']['cpu']:

                    if not_initialized:
                        core_mapping = host_info['resources']['cpu']['core_usage_mapping']
                        number_of_cores = len(core_mapping)
                        current_free = core_mapping[str(current_core)]['free']
                        cpu_core_list = []

                        if c in new_containers:
                            to_allocate = int(c['cpu_max'])
                            cont_cpu_allowance_limit = int(c['cpu_max'])
                            while (to_allocate > 0 and current_core < number_of_cores):
                                if (to_allocate >= 100):
                                    if current_free > 0: cpu_core_list.append(current_core)
                                    core_mapping[str(current_core)][c['container_name']] = current_free
                                    core_mapping[str(current_core)]["free"] -= current_free
                                    to_allocate -= current_free
                                    current_core += 1
                                    if current_core < number_of_cores: current_free = core_mapping[str(current_core)]['free']

                                else:
                                    if current_free > 0: cpu_core_list.append(current_core)
                                    min_usage = min(current_free, to_allocate)
                                    core_mapping[str(current_core)][c['container_name']] = min_usage
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
                            for core in range(0, number_of_cores):
                                if c['container_name'] in core_mapping[str(core)] and core_mapping[str(core)][c['container_name']] > 0:
                                    allocated += core_mapping[str(core)][c['container_name']]
                                    cpu_core_list.append(core)

                            cont_cpu_allowance_limit = allocated

                        cpu_num = get_integer_list_range(cpu_core_list)
                        put_field_data["cpu"] = {"cpu_allowance_limit": cont_cpu_allowance_limit, "cpu_num": cpu_num}

                # Host not in StateDatabase yet
                else:
                    cont_cpu_allowance_limit = int(c['cpu_max'])

                    # cpu_num
                    initial_core = int(total_allowance_allocated // 100)
                    total_allowance_allocated += cont_cpu_allowance_limit
                    last_core = int((total_allowance_allocated - 1) // 100)
                    if last_core > initial_core:
                        cpu_num = str(initial_core) + "-" + str(last_core)
                    else:
                        cpu_num = str(initial_core)

                    put_field_data["cpu"] = {"cpu_allowance_limit": cont_cpu_allowance_limit, "cpu_num": cpu_num}

            if "mem" in resources:
                not_initialized = int(requested_data['mem']['mem_limit']) == -1
                if not_initialized:
                    not_initialized_resources += 1
                    if c in new_containers:
                        cont_mem_limit = int(c['mem_max'])
                    else:
                        # Container already added to the StateDatabase (but not initialized)
                        cont_info = handler.get_structure(c['container_name'])
                        cont_mem_limit = cont_info['resources']['mem']['current']
                        if cont_mem_limit == -1:
                            cont_mem_limit = cont_info['resources']['mem']['max']

                    put_field_data["mem"] = {"mem_limit": cont_mem_limit, "unit": "M"}

            if "disk" in resources and "disk" in c:

                if isinstance(requested_data['disk'], list) and len(requested_data['disk']) == 0:
                    not_initialized = True
                else:
                    not_initialized = int(requested_data['disk']['disk_write_limit']) == -1

                if not_initialized:

                    not_initialized_resources += 1

                    if c in new_containers:
                        cont_disk_limit = int(int(c['disk_max']))
                    else:
                        # Container already added to the StateDatabase (but not initialized)
                        cont_info = handler.get_structure(c['container_name'])
                        cont_disk_limit = cont_info['resources']['disk']['current']
                        if cont_disk_limit == -1: cont_disk_limit = cont_info['resources']['disk']['max']

                    put_field_data["disk"] = {"disk_write_limit": cont_disk_limit, "disk_read_limit": cont_disk_limit, "unit": "Mbit"}

            # if "energy" in resources:
            #     try:
            #         not_initialized = int(requested_data['energy']['energy_limit']) == -1
            #     except KeyError:
            #         not_initialized = True
            #
            #     if not_initialized:
            #         not_initialized_resources += 1
            #         if c in new_containers:
            #             cont_energy_limit = int(c['energy_max'])
            #         else:
            #             # Container already added to the StateDatabase (but not initialized)
            #             cont_info = handler.get_structure(c['container_name'])
            #             cont_energy_limit = cont_info['resources']['energy']['current']
            #             if cont_energy_limit == -1:
            #                 cont_energy_limit = cont_info['resources']['energy']['max']
            #
            #         put_field_data["energy"] = {"energy_limit": cont_energy_limit, "unit": "W"}

            if not_initialized_resources > 0:

                error_message = "Error initializing {0} value for {1} in host {2}".format(', '.join(resources), c['container_name'], host)
                error, response = request_to_state_db(full_url, "put", error_message, put_field_data)

                if not error:
                    print("Container {0} updated with {1}".format(c['container_name'], put_field_data))
                else:
                    # For some reason, the first initialization always results in an error, but it actually works
                    print("Response from node scaler: {0}".format(response.content))
                    print(error_message)
