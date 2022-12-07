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
    guard=False
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
        new_containers = sys.argv[4].split(',')
        with open(sys.argv[5], "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        # Create database if doesnt exist
        if not handler.database_exists(database):
            print("Adding 'structures' documents")
            initializer_utils.create_db(database)
            
        if handler.database_exists(database):
                                        
            ## Container
            for c in new_containers:
                try:
                    old_container = handler.get_structure(c)

                    ## Changing host may be useful later for moving containers between nodes
                    #old_container["host"] = new_host
                    #old_container["host_rescaler_ip"] = new_host
                    #handler.update_structure(old_container)
                except ValueError:
                    # new container
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
                max_cpu_division = int(host_cpu * 100 / len(new_containers))
                max_cpu_percentage_per_container = int(config['max_cpu_percentage_per_container'])
                cpu_allowance_limit = min(max_cpu_division, max_cpu_percentage_per_container)
                free_cpu = host_cpu*100 - (cpu_allowance_limit * len(new_containers))

                max_mem_division = host_mem / len(new_containers)
                max_memory_per_container = int(config['max_memory_per_container'])
                mem_limit = min(max_mem_division, max_memory_per_container)
                free_mem = host_mem - (mem_limit * len(new_containers))

                host = base_host
                host["name"] = new_host
                host["host"] = new_host
                host["resources"] = dict(
                    cpu=dict(max=host_cpu*100, free=free_cpu),
                    mem=dict(max=host_mem, free=free_mem)
                )
                handler.add_structure(host)
