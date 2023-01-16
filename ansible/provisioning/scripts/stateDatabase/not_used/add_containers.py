# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils
import sys
import yaml

base_container = dict(
    type='structure',
    subtype='container',
    guard_policy="serverless",
    host_rescaler_port='8000',
    name="base_container",
    guard=True
)

base_host = dict(
    type='structure',
    subtype='host'
)

# usage example: add_containers.py host0 4 4096 cont0,cont1 config/config.yml

if __name__ == "__main__":

    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "structures"
    
    if (len(sys.argv) > 5):

        new_host = sys.argv[1]
        host_cpu = int(sys.argv[2])
        host_mem = int(sys.argv[3])
        containers = sys.argv[4].split(',')
        with open(sys.argv[5], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        # Create database if doesnt exist
        if not handler.database_exists(database):
            print("Adding 'structures' documents")
            initializer_utils.create_db(database)
            
        if handler.database_exists(database):
                                        
            ## Container
            new_containers = []
            for c in containers:
                try:
                    old_container = handler.get_structure(c)

                    ## Changing host may be useful later for moving containers between nodes
                    #old_container["host"] = new_host
                    #old_container["host_rescaler_ip"] = new_host
                    #handler.update_structure(old_container)
                except ValueError:
                    # new container
                    new_containers.append(c)
                    container = base_container
                    container["name"] = c
                    container["host"] = new_host
                    container["host_rescaler_ip"] = new_host
                    container["resources"] = dict(
                        cpu=dict(max=config['max_cpu_percentage_per_container'], min=config['min_cpu_percentage_per_container'], guard=True),
                        mem=dict(max=config['max_memory_per_container'], min=config['min_memory_per_container'], guard=True)
                    )
                    handler.add_structure(container)

            ## Host
            try:
                old_host = handler.get_structure(new_host)
            except ValueError:
                # new host
                max_shares = host_cpu * 100
                max_cpu_division = int(max_shares / len(containers))
                max_cpu_percentage_per_container = int(config['max_cpu_percentage_per_container'])
                cpu_allowance_limit = min(max_cpu_division, max_cpu_percentage_per_container)

                core_mapping = {}
                for i in range(0,host_cpu,1):
                    core_mapping[str(i)] = {"free": 100}

                max_mem_division = host_mem / len(containers)
                max_memory_per_container = int(config['max_memory_per_container'])
                mem_limit = min(max_mem_division, max_memory_per_container)

                host = base_host
                host["name"] = new_host
                host["host"] = new_host
                host["resources"] = dict(
                    cpu=dict(max=max_shares, free=max_shares, core_usage_mapping=core_mapping),
                    mem=dict(max=host_mem, free=host_mem)
                )
                handler.add_structure(host)

            ## Update Host core mapping
            try:
                host_info = handler.get_structure(new_host)
                current_free_cpu = host_info['resources']['cpu']['free']
                max_cpu = host_info['resources']['cpu']['max']

                if len(new_containers) > 0:
                    max_cpu_division = int(current_free_cpu / len(new_containers))
                else:
                    max_cpu_division = 0
                max_cpu_percentage_per_container = int(config['max_cpu_percentage_per_container'])
                cpu_allowance_limit = min(max_cpu_division, max_cpu_percentage_per_container)

                core_mapping = host_info['resources']['cpu']['core_usage_mapping']
                current_core = 0
                current_free = core_mapping[str(current_core)]['free']

                for c in new_containers:
                    to_allocate = cpu_allowance_limit

                    while (to_allocate > 0 and current_core < host_cpu):
                        if (to_allocate >= 100):
                            core_mapping[str(current_core)][c] = current_free
                            core_mapping[str(current_core)]["free"] -= current_free
                            to_allocate -= current_free
                            current_core += 1
                            if current_core < host_cpu: current_free = core_mapping[str(current_core)]['free']

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
                                if current_core < host_cpu: current_free = core_mapping[str(current_core)]['free']

                print(core_mapping)

                # Update DB
                host_info['resources']['cpu'] = dict(max=max_cpu, free=current_free_cpu, core_usage_mapping=core_mapping)
                handler.update_structure(host_info)
                print("Host updated with")
                print(core_mapping)

            except ValueError:
                # new host
                print("Host " + new_host + " doesn't exist")
