# Scripts

This folder contains auxiliary scripts for deployment, configuration, and maintenance.

## Main entrypoints

- `start_all.sh`: starts the entire environment.
- `stop_all.sh`: stops the entire environment.
- `restart_services.sh`: ensures that all services are up and running.
- `stop_containers.sh`: stops all running containers.
- `set_env.sh`: sets the environment for the scripts above.
- `load_apps_from_config.py`: loads the configured apps into the StateDatabase.

## Subfolders

- `system/`: system scripts (e.g., LV extensions).
- `config/`: loading and synchronizing configuration and inventory.
- `network/`: network related utilities.
- `hosts/`: operations on hosts/nodes and system resources.
- `state_database/`: scripts related to the StateDatabase.
- `state_database/deprecated/`: old or unmaintained scripts.