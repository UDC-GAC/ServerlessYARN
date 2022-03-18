# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils
import sys

base_container = dict(
    type='structure',
    subtype='container',
    guard_policy="serverless",
    host='host0',
    host_rescaler_ip='host0',
    host_rescaler_port='8000',
    name="base_container",
    guard=False,
    resources=dict(
        cpu=dict(max=400, min=50, guard=True),
        mem=dict(max=8192, min=1024, guard=True)
    )
)

# usage example: add_container.py app1 host0 cont0,cont1

if __name__ == "__main__":

    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "structures"    
    
    new_app = sys.argv[1]
    new_host = sys.argv[2]
    new_containers = sys.argv[3].split(',')
    
    # Create database if doesnt exist
    if not handler.database_exists(database):
        print("Adding 'structures' documents")
        initializer_utils.create_db(database)
        
    if handler.database_exists(database):
                                    
	## Container
        for c in new_containers:
            try:
                old_container = handler.get_structure(c)
                old_container["host"] = new_host
                old_container["host_rescaler_ip"] = new_host
                handler.update_structure(old_container)
            except ValueError:
                # new container           
                container = dict(base_container)
                container["name"] = c
                container["host"] = new_host
                container["host_rescaler_ip"] = new_host
                handler.add_structure(container)

        ## Host
        try:
            old_host = handler.get_structure(new_host)
            #handler.update_structure(old_host)
        except ValueError:
            # new host
            host = dict(type='structure',
                subtype='host',
                name=new_host,
                host=new_host,
                resources=dict(
                    #cpu=dict(max=400, free=0,
                    #         core_usage_mapping={
                    #             "0": {"cont0": 100, "free": 0},
                    #             "1": {"cont0": 100, "free": 0},
                    #             "2": {"cont1": 100, "free": 0},
                    #             "3": {"cont1": 100, "free": 0}
                    #         }),
                    mem=dict(max=16384, free=0)
                )
            )
            handler.add_structure(host)

        ## App
        try:
            old_app = handler.get_structure(new_app)
            for c in new_containers:
                if c not in old_app["containers"]:
                    old_app["containers"].append(c)
            handler.update_structure(old_app)
        except ValueError:
            # new app
            app = dict(
                type='structure',
                subtype='application',
                name=new_app,
                guard=True,
                guard_policy="serverless",
                resources=dict(
                    cpu=dict(max=400, min=100, guard=False),
                   mem=dict(max=8196, min=2048, guard=False)
                ),
                containers = new_containers
            )
            handler.add_structure(app)

    
