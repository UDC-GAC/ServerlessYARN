# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils
import sys

# usage example: add_host.py host0

if __name__ == "__main__":

    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "structures"    
    
    new_host = sys.argv[1]
    
    # Create database if doesnt exist
    if not handler.database_exists(database):
        print("Adding 'structures' documents")
        initializer_utils.create_db(database)
        
    if handler.database_exists(database): 

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

    
