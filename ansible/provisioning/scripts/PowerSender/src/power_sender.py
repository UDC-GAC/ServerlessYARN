import os
import sys
import time
import yaml
import requests
import logging
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager

from src.apptainer.ApptainerHandler import ApptainerHandler
from src.utils.MyUtils import create_dir, clean_log_file

SCRIPT_PATH = os.path.abspath(__file__)
SMARTWATTS_DIR = os.path.dirname(os.path.dirname(SCRIPT_PATH))
PROVISIONING_DIR = os.path.dirname(os.path.dirname(SMARTWATTS_DIR))
ANSIBLE_CONFIG_FILE = f"{PROVISIONING_DIR}/config/config.yml"
ANSIBLE_INVENTORY_FILE = f"{PROVISIONING_DIR}/../ansible.inventory"
LOG_DIR = f"{SMARTWATTS_DIR}/log"
LOG_FILE = f"{LOG_DIR}/power_sender.log"


logger = logging.getLogger("power_sender")

def get_nodes():
    loader = DataLoader()
    ansible_inventory = InventoryManager(loader=loader, sources=ANSIBLE_INVENTORY_FILE)
    return ansible_inventory.get_groups_dict()['nodes']

if __name__ == "__main__":

    if len(sys.argv) < 4:
        raise Exception("Missing some arguments: power_sender.py <SINGULARITY_COMMAND_ALIAS> <SMARTWATTS_OUTPUT> <SAMPLING_FREQUENCY>")

    singularity_command_alias = sys.argv[1]
    smartwatts_output = sys.argv[2]
    sampling_frequency = int(sys.argv[3])

    with open(ANSIBLE_CONFIG_FILE, "r") as f:
        ansible_config = yaml.load(f, Loader=yaml.FullLoader)

    create_dir(LOG_DIR)
    clean_log_file(LOG_DIR, LOG_FILE)
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(levelname)s (%(name)s): %(asctime)s %(message)s')

    # Get running containers on node
    apptainer_handler = ApptainerHandler(command=singularity_command_alias, privileged=True)

    # Get current timestamp UTC
    start_timestamp = datetime.now(timezone.utc)
    logger.info(f"Start time: {start_timestamp}")

    # Get session to OpenTSDB
    opentsdb_url = "http://{0}:{1}/api/put".format(ansible_config['server_ip'], ansible_config['opentsdb_port'])
    headers = {'Content-Type': 'application/json'}
    session = requests.Session()

    # Read SmartWatts output and get targets
    output_file = {}
    last_read_position = {}
    while True:
        try:
            current_nodes = get_nodes()
            iter_count = {"targets": 0, "lines": 0}
            t_start = time.perf_counter_ns()
            for container in apptainer_handler.get_remote_running_containers_list(current_nodes):

                cont_pid = container["pid"]
                cont_name = container["name"]

                # If target is not registered, initialize it
                if cont_pid not in output_file:
                    logger.info(f"Found new target with name {cont_name} and pid {cont_pid}. Registered.")
                    output_file[cont_pid] = f"{smartwatts_output}/sensor-apptainer-{cont_pid}/PowerReport.csv"
                    last_read_position[cont_pid] = 0

                if not os.path.isfile(output_file[cont_pid]) or not os.access(output_file[cont_pid], os.R_OK):
                    logger.warning(f"Couldn't access file from target {container['name']}: {output_file[cont_pid]}")
                    continue

                # Read target output
                with open(output_file[cont_pid], 'r') as file:
                    # If file is empty, skip
                    if os.path.getsize(output_file[cont_pid]) <= 0:
                        logger.warning(f"Target {cont_name} file is empty: {output_file[cont_pid]}")
                        continue

                    # Go to last read position
                    file.seek(last_read_position[cont_pid])

                    # Skip header
                    if last_read_position[cont_pid] == 0:
                        next(file)

                    lines = file.readlines()
                    if len(lines) == 0:
                        logger.warning(f"There aren't new lines to process for target {cont_name}")
                        continue

                    iter_count["targets"] += 1
                    iter_count["lines"] += len(lines)
                    last_read_position[cont_pid] = file.tell()

                    # Gather data from target output
                    bulk_data = []
                    for line in lines:
                        # line example: <timestamp> <sensor> <target> <value> ...
                        fields = line.strip().split(',')
                        num_fields = len(fields)
                        if num_fields < 4:
                            raise Exception(f"Missing some fields in SmartWatts output for "
                                            f"target {cont_name} ({num_fields} out of 4 expected fields)")
                        # SmartWatts timestamps are 2 hours ahead from UTC (UTC-02:00)
                        # Normalize timestamps to UTC (actually UTC-02:00) and add 2 hours to get real UTC
                        data = {
                            "timestamp": datetime.fromtimestamp(int(fields[0]) / 1000, timezone.utc) + timedelta(hours=2),
                            "value": float(fields[3]),
                            "cpu": int(fields[4])
                        }
                        # Only data obtained after the start of this program are sent
                        if data["timestamp"] < start_timestamp:
                            continue
                        bulk_data.append(data)

                    # Aggregate data by cpu (mean) and timestamp (sum)
                    if len(bulk_data) > 0:
                        agg_data = pd.DataFrame(bulk_data).groupby(['timestamp', 'cpu']).agg({'value': 'mean'}).reset_index().groupby('timestamp').agg({'value': 'sum'}).reset_index()

                        # Format data into a dict to dump into a JSON
                        target_metrics = [
                            {"metric": "structure.energy.usage", "tags": {"host": cont_name}, "timestamp": int(row['timestamp'].timestamp() * 1000), "value": row['value']}
                            for _, row in agg_data .iterrows()
                        ]

                        try:
                            # Send data to OpenTSDB
                            r = session.post(opentsdb_url, data=json.dumps(target_metrics), headers=headers)
                            if r.status_code != 204:
                                print("Error while sending container {0} metrics to OpenTSDB. Sent data: {1}".format(cont_name, data))
                                r.raise_for_status()
                        except Exception as e:
                            logger.error(f"Error sending data to OpenTSDB: {e}")

            t_stop = time.perf_counter_ns()
            delay = (t_stop - t_start) / 1e9
            logger.info(f"Processed {iter_count['targets']} targets and {iter_count['lines']} lines causing a delay of {delay} seconds")

            # Avoids negative sleep times when there is a high delay
            if delay > sampling_frequency:
                logger.warning(f"High delay ({delay}) causing negative sleep times. Waiting until the next {sampling_frequency}s cycle")
                delay = delay % sampling_frequency
            time.sleep(sampling_frequency - delay)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")