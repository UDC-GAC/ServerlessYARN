# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils
import sys
import json

# usage example: update_host.py host0 '{"0":{"cont0":100,"free":0},"1":{"cont1":100,"free":0},"2":{"cont2":100,"free":0},"3":{"cont3":100,"free":0}}'

if __name__ == "__main__":

    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "structures"    
    
    print(sys.argv[2])
    new_host = sys.argv[1]
    core_mapping = json.loads(sys.argv[2])
    
    # Create database if doesnt exist
    if not handler.database_exists(database):
        print("Adding 'structures' documents")
        initializer_utils.create_db(database)
        
    if handler.database_exists(database): 

        ## Host
        try:
            old_host = handler.get_structure(new_host)
            old_host['resources']['cpu'] = dict(max=400, free=0, core_usage_mapping=core_mapping)
            handler.update_structure(old_host)
            print("Host updated with")
            print(core_mapping)
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

    
