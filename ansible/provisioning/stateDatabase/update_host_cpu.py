# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils
import sys
import json

# usage example: update_host_cpu.py host0 4 cont0,cont1 true

if __name__ == "__main__":

    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "structures"    
    
    host = sys.argv[1]
    number_of_cores = int(sys.argv[2])
    new_containers = sys.argv[3].split(',')
    replace = sys.argv[4] == "true"

    core_mapping = {}

    ## New algorithm
    for i in range(0,number_of_cores,1): 
        core_mapping[str(i)] = {"free": 0}

    cpu_allowance_limit = int(number_of_cores * 100 / len(new_containers))
    current_core = 0
    current_free = 100

    for c in new_containers:
        to_allocate = cpu_allowance_limit

        while (to_allocate > 0 and current_core < number_of_cores):
            if (to_allocate >= 100):
                core_mapping[str(current_core)][c] = current_free
                to_allocate -= current_free
                current_core += 1
                current_free = 100

            else:
                min_usage = min(current_free, to_allocate)
                core_mapping[str(current_core)][c] = min_usage
                if (min_usage == to_allocate):
                    ## we continue in current core
                    current_free -= to_allocate
                    to_allocate = 0
                else:
                    ## we switch to next core
                    to_allocate -= current_free
                    current_core += 1
                    current_free = 100

    print(core_mapping)

    # Create database if doesnt exist
    if not handler.database_exists(database):
        print("Adding 'structures' documents")
        initializer_utils.create_db(database)
        
    if handler.database_exists(database): 

        ## Host
        try:
            old_host = handler.get_structure(host)

            if ('cpu' in old_host['resources'] and not replace):
                print("CPU information already in host " + host + " and not replacing")

            else:
                old_host['resources']['cpu'] = dict(max=number_of_cores*100, free=0, core_usage_mapping=core_mapping)
                handler.update_structure(old_host)
                print("Host updated with")
                print(core_mapping)

        except ValueError:
            # new host
            print("Host " + host + " doesn't exist")

    
