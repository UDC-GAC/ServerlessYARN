# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils

energy_exceeded_upper = dict(
    _id='energy_exceeded_upper',
    type='rule',
    resource="energy",
    name='energy_exceeded_upper',
    rule=dict(
        {"and": [
            {">": [
                {"var": "energy.structure.energy.usage"},
                {"var": "energy.structure.energy.max"}]}]}),
    generates="events", action={"events": {"scale": {"down": 1}}},
    active=True
)

energy_dropped_lower_and_cpu_exceeded_upper = dict(
    _id='energy_dropped_lower_and_cpu_exceeded_upper',
    type='rule',
    resource="energy",
    name='energy_dropped_lower_and_cpu_exceeded_upper',
    rule=dict(
        {"and": [
            {"<": [
                {"var": "energy.structure.energy.usage"},
                {"var": "energy.structure.energy.max"}]},
            {">": [
                {"var": "cpu.structure.cpu.usage"},
                {"var": "cpu.limits.cpu.upper"}]}]}),
    generates="events", action={"events": {"scale": {"up": 1}}},
    active=True
)

EnergyRescaleDown = dict(
    _id='EnergyRescaleDown',
    type='rule',
    resource="energy",
    name='EnergyRescaleDown',
    rule=dict(
        {"and": [
            {"<=": [
                {"var": "events.scale.up"},
                1]},
            {">=": [
                {"var": "events.scale.down"},
                5]}
        ]}),
    generates="requests",
    events_to_remove=5,
    action={"requests": ["CpuRescaleDown"]},
    amount=-20,
    rescale_policy="modelling",
    rescale_type="down",
    active=True
)

EnergyRescaleUp = dict(
    _id='EnergyRescaleUp',
    type='rule',
    resource="energy",
    name='EnergyRescaleUp',
    rule=dict(
        {"and": [
            {">=": [
                {"var": "events.scale.up"},
                4]},
            {"<=": [
                {"var": "events.scale.down"},
                1]}
        ]}),
    generates="requests",
    events_to_remove=4,
    action={"requests": ["CpuRescaleUp"]},
    amount=20,
    rescale_policy="modelling",
    rescale_type="up",
    active=True
)

if __name__ == "__main__":
    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "rules"
    initializer_utils.remove_db(database)
    initializer_utils.create_db(database)
    if handler.database_exists("rules"):
        print("Adding rules for tests")
        handler.add_rule(energy_exceeded_upper)
        handler.add_rule(EnergyRescaleDown)
        handler.add_rule(energy_dropped_lower_and_cpu_exceeded_upper)
        handler.add_rule(EnergyRescaleUp)
