# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils
import sys

applications = ["app1"]

base_limits = dict(
        type='limit',
        name="base_container",
        resources=dict(
            cpu=dict(upper=100, lower=50, boundary=25),
            mem=dict(upper=2048, lower=512, boundary=256)
        )
    )

# example usage: add_limits.py cont0 cont1 cont2 cont3

if __name__ == "__main__":

    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "limits"    
    
    containers = []
    
    n = len(sys.argv)
    for i in range(1, n):
        c = sys.argv[i]
        containers.append(c)
    
    # Create database if doesnt exist
    if not handler.database_exists(database):
        print("Adding 'limits' documents")
        initializer_utils.create_db(database)
        
    if handler.database_exists(database):    
    
        for c in containers:
            try:
                cont = handler.get_structure(c)
                old_limits = handler.get_limits(cont)
                old_limits['resources'] = dict(
                      cpu=dict(upper=100, lower=50, boundary=25),
                      mem=dict(upper=2048, lower=512, boundary=256)
                )
                handler.update_limit(old_limits)
            except ValueError:
                limits = dict(base_limits)
                limits["name"] = c
                handler.add_limit(limits)
        try:
            app = handler.get_structure("app1")
            old_limits = handler.get_limits(app)
            handler.update_limit(old_limits)
        except ValueError:
            limits = dict(
                type='limit',
                name='app1',
                resources=dict(
                    cpu=dict(upper=200, lower=100, boundary=50)
                )
            )
            handler.add_limit(limits)
        
