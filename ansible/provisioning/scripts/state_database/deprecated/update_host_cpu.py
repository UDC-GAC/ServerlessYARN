# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils
import sys
import json
import yaml

# usage example: update_host_cpu.py host0 4 cont0,cont1 true config/config.yml

if __name__ == "__main__":

    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "structures"
    
    if (len(sys.argv) > 4):

        host = sys.argv[1]
        number_of_cores = int(sys.argv[2])
        containers = sys.argv[3].split(',')
        replace = sys.argv[4] == "true"
        with open(sys.argv[5], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        # Create database if doesnt exist
        if not handler.database_exists(database):
            print("Adding 'structures' documents")
            initializer_utils.create_db(database)
            
        if handler.database_exists(database): 

            ## Host
            try:
                host_info = handler.get_structure(host)

                #if ('cpu' in host_info['resources'] and not replace):
                #    print("CPU information already in host " + host + " and not replacing")

                # Get only new containers
                new_containers = []
                for cont in containers:
                    try:
                        added_cont = handler.get_structure(cont)
                        current_cpu = added_cont['resources']['cpu']['current']
                    except ValueError:
                        # new container
                        new_containers.append(cont)
                    except KeyError:
                        # just added container
                        new_containers.append(added_cont['name'])


                current_free_cpu = host_info['resources']['cpu']['free']
                max_cpu = host_info['resources']['cpu']['max']

                #max_cpu_division = int(number_of_cores * 100 / len(new_containers))
                if len(new_containers) > 0:
                    max_cpu_division = int(current_free_cpu / len(new_containers))
                else:
                    max_cpu_division = 0
                max_cpu_percentage_per_container = int(config['max_cpu_percentage_per_container'])
                cpu_allowance_limit = min(max_cpu_division, max_cpu_percentage_per_container)
                #free_cpu = number_of_cores*100 - (cpu_allowance_limit * len(new_containers))
                free_cpu = current_free_cpu - (cpu_allowance_limit * len(new_containers))

                core_mapping = {}

                ## New algorithm
                core_mapping = host_info['resources']['cpu']['core_usage_mapping']

                #max_cpu_division = int(number_of_cores * 100 / len(new_containers))
                #max_cpu_percentage_per_container = int(config['max_cpu_percentage_per_container'])
                #cpu_allowance_limit = min(max_cpu_division, max_cpu_percentage_per_container)
                current_core = 0
                #current_free = 100
                current_free = core_mapping[str(current_core)]['free']

                for c in new_containers:
                    to_allocate = cpu_allowance_limit

                    while (to_allocate > 0 and current_core < number_of_cores):
                        if (to_allocate >= 100):
                            core_mapping[str(current_core)][c] = current_free
                            core_mapping[str(current_core)]["free"] -= current_free
                            to_allocate -= current_free
                            current_core += 1
                            #current_free = 100
                            if current_core < number_of_cores: current_free = core_mapping[str(current_core)]['free']

                        else:
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
                                #current_free = 100
                                if current_core < number_of_cores: current_free = core_mapping[str(current_core)]['free']

                print(core_mapping)

                # Update DB
                #host_info['resources']['cpu'] = dict(max=number_of_cores*100, free=free_cpu, core_usage_mapping=core_mapping)
                host_info['resources']['cpu'] = dict(max=max_cpu, free=free_cpu, core_usage_mapping=core_mapping)
                handler.update_structure(host_info)
                print("Host updated with")
                print(core_mapping)

            except ValueError:
                # new host
                print("Host " + host + " doesn't exist")




