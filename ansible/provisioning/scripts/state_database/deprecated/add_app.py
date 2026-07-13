# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils
import sys

# usage example: add_app.py app1

if __name__ == "__main__":

    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "structures"    
    
    new_app = sys.argv[1]
    
    # Create database if doesnt exist
    if not handler.database_exists(database):
        print("Adding 'structures' documents")
        initializer_utils.create_db(database)
        
    if handler.database_exists(database):

        ## App
        try:
            old_app = handler.get_structure(new_app)
            #handler.update_structure(old_app)
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
                containers = []
            )
            handler.add_structure(app)

    
