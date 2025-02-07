# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils

# Check if we have a gap to scale down CPU (current - min >= 25) and whether cpu usage is low (usage / current < 0.4)
cpu_usage_low = dict(
    _id='cpu_usage_low',
    type='rule',
    resource="cpu",
    name='cpu_usage_low',
    rule=dict(
        {"and": [
            {">=": [
                {"-": [
                    {"var": "cpu.structure.cpu.current"},
                    {"var": "cpu.structure.cpu.min"}]
                },
                25
            ]},
            {"<": [
                {"/": [
                    {"var": "cpu.structure.cpu.usage"},
                    {"var": "cpu.structure.cpu.current"}]
                },
                0.4
            ]}
        ]}
    ),
    active=False,
    generates="",
)

# Check if we have a gap to scale up CPU (max - current >= 25) and whether cpu usage is high (usage / current > 0.7)
cpu_usage_high = dict(
    _id='cpu_usage_high',
    type='rule',
    resource="cpu",
    name='cpu_usage_high',
    rule=dict(
        {"and": [
            {">=": [
                {"-": [
                    {"var": "cpu.structure.cpu.max"},
                    {"var": "cpu.structure.cpu.current"}]
                },
                25
            ]},
            {">": [
                {"/": [
                    {"var": "cpu.structure.cpu.usage"},
                    {"var": "cpu.structure.cpu.current"}]
                },
                0.7
            ]}
        ]}
    ),
    active=False,
    generates="",
)

if __name__ == "__main__":
    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "rules"
    if handler.database_exists("rules"):
        print("Adding rules for tests")
        handler.add_rule(cpu_usage_low)
        handler.add_rule(cpu_usage_high)
