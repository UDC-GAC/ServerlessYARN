import os
import json
import sys
import time
import yaml
import requests
from datetime import datetime, timedelta

POLLING_FREQUENCY = 5

if __name__ == "__main__":

    if len(sys.argv) < 1:
        raise Exception("Missing some arguments: send_power_opentsdb.py <smartwatts_output_dir>")

    smartwatts_output = sys.argv[1]
    script_path = os.path.abspath(__file__)
    provisioning_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
    with open(f"{provisioning_dir}/config/config.yml", "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    # Get session to OpenTSDB
    opentsdb_url = "http://{0}:{1}/api/put".format(config['server_ip'], config['opentsdb_port'])
    headers = {'Content-Type': 'application/json'}
    session = requests.Session()

    # Read SmartWatts output and get targets
    output_file = {}
    last_read_position = {}
    while True:
        for target_dir in os.listdir(smartwatts_output):
            target_name = target_dir[7:] # Remove "sensor-"
            if target_name not in output_file: # New target
                print(f"Found new target with name {target_name} and dir {target_dir}. Registered")
                output_file[target_name] = f"{smartwatts_output}/{target_dir}/PowerReport.csv"
                last_read_position[target_name] = 0

            with open(output_file[target_name], 'r') as file:
                # If file is empty, skip
                if os.path.getsize(output_file[target_name]) <= 0:
                    continue

                # Skip header
                file.seek(last_read_position[target_name])
                if last_read_position[target_name] == 0:
                    next(file)

                lines = file.readlines()
                if len(lines) == 0:
                    print("There aren't new lines to process for target {0}".format(target_name))
                    continue
                print("Processing {0} lines for target {1}".format(len(lines), target_name))
                last_read_position[target_name] = file.tell()
                data = {"metric": "structure.energy.usage", "tags": {"host": target_name}}

                # line example: <timestamp> <sensor> <target> <value> ...
                for line in lines:
                    fields = line.strip().split(',')
                    num_fields = len(fields)

                    if num_fields < 4:
                        raise Exception("Missing some fields in SmartWatts output for "
                                        "target {0} ({1} out of 4 expected fields)".format(target_name, num_fields))
                    # Verify that the target file actually corresponds to the metrics of that target
                    if target_name != str(fields[2]):
                        raise Exception("Found metrics from target {0} in a file supposed"
                                        " to store metrics from target {1}".format(str(fields[2]), target_name))

                    # Add 2 hours to the timestamp
                    # For some reason SmartWatts timestamps are set two hours ahead (even taking into account the timezone)
                    timestamp = datetime.fromtimestamp(int(fields[0]) / 1000) + timedelta(hours=2)
                    data["timestamp"] = int(timestamp.timestamp() * 1000)
                    data["value"] = float(fields[3])

                    
                    r = session.post(opentsdb_url, data=json.dumps(data), headers=headers)
                    if r.status_code != 204:
                        print("Error while sending target {0} metrics to OpenTSDB. Sent data: {1}".format(target_name, data))
                        r.raise_for_status()
                #print(lines[-1:])
                #print(data)

        time.sleep(POLLING_FREQUENCY)
