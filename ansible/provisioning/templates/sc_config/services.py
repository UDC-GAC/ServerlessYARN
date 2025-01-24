# /usr/bin/python
import src.StateDatabase.couchdb as couchDB
import src.StateDatabase.utils as couchdb_utils

# TODO: Check use cases to add mem in GUARDABLE_RESOURCES
guardian = dict(
    name="guardian",
    type="service",
    heartbeat="",
    config=dict(
        ACTIVE=False,
        DEBUG=True,
        EVENT_TIMEOUT=60,
        WINDOW_DELAY=20,
        WINDOW_TIMELAPSE=10,
        GUARDABLE_RESOURCES=["cpu"{% if disk_capabilities and disk_rescaling %}, "disk"{% endif %}{% if power_budgeting %}, "energy"{% endif %}]
    )
)

scaler = dict(
    name="scaler",
    type="service",
    heartbeat="",
    config=dict(
        ACTIVE=False,
        DEBUG=True,
        REQUEST_TIMEOUT=60,
        POLLING_FREQUENCY=5
    )
)

database_snapshoter = dict(
    name="database_snapshoter",
    type="service",
    heartbeat="",
    config=dict(
        ACTIVE=False,
        DEBUG=True
    )
)

structures_snapshoter = dict(
    name="structures_snapshoter",
    type="service",
    heartbeat="",
    config=dict(
        ACTIVE=False,
        DEBUG=True,
        RESOURCES_PERSISTED=["cpu", "mem"{% if disk_capabilities and disk_rescaling %}, "disk"{% endif %}{% if power_budgeting %}, "energy"{% endif %}]
    )
)

refeeder = dict(
    name="refeeder",
    type="service",
    heartbeat="",
    config=dict(
        ACTIVE=False,
        DEBUG=True,
        GENERATED_METRICS=["cpu", "mem"{% if disk_capabilities and disk_rescaling %}, "disk"{% endif %}{% if power_budgeting %}, "energy"{% endif %}]
    )
)

sanity_checker = dict(
    name="sanity_checker",
    type="service",
    heartbeat="",
    config=dict(
        DELAY=30,
        DEBUG=True
    )
)

rebalancer  = dict(
    name="rebalancer",
    type="service",
    heartbeat="",
    config=dict(
        DEBUG=True,
        RESOURCES_BALANCED=["cpu"{% if disk_capabilities and disk_rescaling %}, "disk"{% endif %}],
        STRUCTURES_BALANCED=["applications"],
        BALANCING_METHOD="pair_swapping",
        WINDOW_DELAY=10,
        WINDOW_TIMELAPSE=35,
    )
)

{% if power_budgeting -%}
# Aditional services for power_budgeting
energy_manager = dict(
    name="energy_manager",
    type="service",
    heartbeat="",
    config=dict(
        POLLING_FREQUENCY=10,
        DEBUG=True
    )
)

{% if online_learning -%}
watt_trainer = dict(
    name="watt_trainer",
    type="service",
    heartbeat="",
    config=dict(
        WINDOW_TIMELAPSE={{ power_sampling_frequency }},
        DEBUG=True
    )
)

{%- endif %}
{%- endif %}

if __name__ == "__main__":
    initializer_utils = couchdb_utils.CouchDBUtils()
    handler = couchDB.CouchDBServer()
    database = "services"
    initializer_utils.remove_db(database)
    initializer_utils.create_db(database)

    if handler.database_exists("services"):
        print("Adding 'services' document")
        handler.add_service(scaler)
        handler.add_service(guardian)
        handler.add_service(database_snapshoter)
        handler.add_service(structures_snapshoter)
        handler.add_service(refeeder)
        handler.add_service(sanity_checker)
        handler.add_service(rebalancer)

        {% if power_budgeting -%}
        # Aditional services for power_budgeting
        handler.add_service(energy_manager)
        {% if online_learning -%}
        handler.add_service(watt_trainer)
        {%- endif %}
        {%- endif %}
