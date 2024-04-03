import json
import sys
import time
import yaml
import requests
from datetime import datetime

POLLING_FREQUENCY = 5

if __name__ == "__main__":

    if len(sys.argv) < 3:
        raise Exception("Missing some arguments: send_power_opentsdb.py <smartwatts_output_dir> <targets> <ansible_config>")

    smartwatts_output = sys.argv[1]
    targets = sys.argv[2].split(",")
    print(targets)
    with open(sys.argv[3], "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    # Set CSV files to read data from
    output_file = {}
    last_read_position = {}
    for target in targets:
        output_file[target] = f"{smartwatts_output}/sensor-{target}/PowerReport.csv"
        last_read_position[target] = 0

    # Get session to OpenTSDB
    opentsdb_url = "http://{0}:{1}/api/put".format(config['server_ip'], config['opentsdb_port'])
    headers = {'Content-Type': 'application/json'}
    session = requests.Session()

    while True:
        for target in targets:
            with open(output_file[target], 'r') as file:
                file.seek(last_read_position[target])
                if last_read_position[target] == 0:
                    next(file)
                lines = file.readlines()
                if len(lines) == 0:
                    print("There aren't new lines to process for target {0}".format(target))
                    continue
                last_read_position[target] = file.tell()
                data = {"metric": "structure.energy.usage", "tags": {"host": target}}

                # line example: <timestamp> <sensor> <target> <value> ...
                for line in lines:
                    fields = line.strip().split(',')
                    num_fields = len(fields)

                    if num_fields < 4:
                        raise Exception("Missing some fields in SmartWatts output for "
                                        "target {0} ({1} out of 4 expected fields)".format(target, num_fields))
                    # Verify that the target file actually corresponds to the metrics of that target
                    if target != str(fields[2]):
                        raise Exception("Found metrics from target {0} in a file supposed"
                                        " to store metrics from target {1}".format(str(fields[2]), target))

                    data["timestamp"] = int(datetime.now().timestamp() * 1000)
                    data["value"] = float(fields[3])

                    r = session.post(opentsdb_url, data=json.dumps(data), headers=headers)
                    if r.status_code != 204:
                        print("Error while sending target {0} metrics to OpenTSDB. Sent data: {1}".format(target, data))
                        r.raise_for_status()

        time.sleep(POLLING_FREQUENCY)
