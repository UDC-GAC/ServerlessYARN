# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils
import sys

cont_base_limits = dict(
        type='limit',
        name="base_container",
        resources=dict(
            cpu=dict(upper=100, lower=50, boundary=25),
            mem=dict(upper=2048, lower=512, boundary=256)
        )
    )

app_base_limits = dict(
        type='limit',
        name="base_app",
        resources=dict(
            cpu=dict(upper=200, lower=100, boundary=50)
        )
    )

# example usage: add_limits.py cont0 cont1 cont2 app1

if __name__ == "__main__":

    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "limits"    
    
    structures = []
    
    n = len(sys.argv)
    for i in range(1, n):
        c = sys.argv[i]
        structures.append(c)
    
    # Create database if doesnt exist
    if not handler.database_exists(database):
        print("Adding 'limits' documents")
        initializer_utils.create_db(database)
        
    if handler.database_exists(database):    
    
        for s in structures:

            try:
                struct = handler.get_structure(s)

                try:
                    old_limits = handler.get_limits(struct)
                except ValueError:

                    if (struct['subtype'] in ["container","application"]):
                
                        limits = {}

                        if (struct['subtype'] == "container"):
                            limits = dict(cont_base_limits)

                        elif (struct['subtype'] == "application"):
                            limits = dict(app_base_limits)
                        
                        limits["name"] = s
                        handler.add_limit(limits)

            except ValueError:
                print("Error: structure " + s + " does not exist")
