import logging.handlers
import os
import sys
import time
import yaml
import logging
import pandas as pd
from datetime import datetime, timezone, timedelta
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager

from src.apptainer.ApptainerHandler import ApptainerHandler
from src.opentsdb.OpenTSDBHandler import OpenTSDBHandler
from src.utils.MyUtils import MyUtils

SCRIPT_PATH = os.path.abspath(__file__)
POWER_SENDER_DIR = os.path.dirname(os.path.dirname(SCRIPT_PATH))
PROVISIONING_DIR = os.path.dirname(os.path.dirname(POWER_SENDER_DIR))
ANSIBLE_CONFIG_FILE = f"{PROVISIONING_DIR}/config/config.yml"
ANSIBLE_INVENTORY_FILE = f"{PROVISIONING_DIR}/../ansible.inventory"
LOG_DIR = f"{POWER_SENDER_DIR}/log"
LOG_FILE = f"{LOG_DIR}/power_sender.log"
MAX_LOG_SIZE = 10  # Max log file size in MB


class PowerSender:

    def __init__(self, verbose, singularity_command_alias, smartwatts_output, sampling_frequency):
        self.verbose = verbose

        # SmartWatts output directory
        self.smartwatts_output = smartwatts_output

        # Sampling frequency to read and send data
        self.sampling_frequency = sampling_frequency

        # Logger to print information
        self.logger = None

        # Start timestamp to send only data obtained after the start of this program
        self.start_timestamp = None

        # Dictionary to store information about Ansible configuration
        self.ansible_info = None

        # Apptainer handler to get running containers
        self.apptainer_handler = ApptainerHandler(command=singularity_command_alias, privileged=True)

        # OpenTSDB handler to send data
        self.opentsdb_handler = None

        # Dictionary to store output files and their last read position
        self.cont_output_files = {}

        # Dictionary to store information about the current iteration
        self.iter_info = {}

        # Delay between iterations
        self.delay = 0

    @staticmethod
    def remove_outliers(df, column):
        if df.empty:
            return df
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        return df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]

    @staticmethod
    def aggregate_data(bulk_data, cont_name):
        # Aggregate data by cpu (mean) and timestamp (sum)
        agg_data = pd.DataFrame(bulk_data).groupby(['timestamp', 'cpu']).agg({'value': 'mean'}).reset_index().groupby('timestamp').agg({'value': 'sum'}).reset_index()
        # TODO: Set a buffer to take into account more metrics when computing the outliers
        agg_data = PowerSender.remove_outliers(agg_data, 'value')

        # Format data into a dict to dump into a JSON
        return [
            {"metric": "structure.energy.usage", "tags": {"host": cont_name}, "timestamp": int(row['timestamp'].timestamp() * 1000), "value": row['value']}
            for _, row in agg_data .iterrows()
        ]

    def __init_logging_config(self):
        # Create/clean log directory and files
        MyUtils.create_dir(LOG_DIR)
        MyUtils.clean_log_files(LOG_DIR)

        # Set handler to rotate log files and formatter
        handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=MAX_LOG_SIZE*1024*1024, backupCount=3)
        formatter = logging.Formatter('%(levelname)s (%(name)s): %(asctime)s %(message)s')
        handler.setFormatter(formatter)

        # Set logger
        self.logger = logging.getLogger("power_sender")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(handler)

    def __set_start_timestamp(self):
        self.start_timestamp = datetime.now(timezone.utc)
        self.logger.info(f"Start time: {self.start_timestamp}")

    def __set_ansible_info(self):
        with open(ANSIBLE_CONFIG_FILE, "r") as f:
            ansible_config = yaml.load(f, Loader=yaml.FullLoader)
        loader = DataLoader()
        ansible_inventory = InventoryManager(loader=loader, sources=ANSIBLE_INVENTORY_FILE)
        self.ansible_info = {
            "opentsdb_addr": ansible_config['server_ip'],
            "opentsdb_port": ansible_config['opentsdb_port'],
            "nodes": ansible_inventory.get_groups_dict()['nodes']
        }

    def __add_iter_info(self, lines):
        self.iter_info["targets"] += 1
        self.iter_info["lines"] += len(lines)

    def __reset_iter_info(self):
        self.iter_info = {"targets": 0, "lines": 0}

    def print_iter_info(self):
        self.logger.info(f"Processed {self.iter_info['targets']} targets and "
                         f"{self.iter_info['lines']} lines causing a delay of {self.delay} seconds")

    def adjust_sleep_time(self):
        if self.delay > self.sampling_frequency:
            self.logger.warning(f"High delay ({self.delay}) causing negative sleep times. "
                                f"Waiting until the next {self.sampling_frequency}s cycle")
            self.delay = self.delay % self.sampling_frequency

    def get_container_output_file(self, name, pid):
        # If container is not registered, initialize it
        if pid not in self.cont_output_files:
            self.logger.info(f"Found new target with name {name} and pid {pid}. Registered.")
            self.cont_output_files[pid] = {
                "path": f"{smartwatts_output}/sensor-apptainer-{pid}/PowerReport.csv",
                "position": 0
            }

        return self.cont_output_files[pid]["path"]

    def read_container_output(self, path, cont_name, cont_pid):
        with open(path, 'r') as file:
            # If file is empty, skip
            if os.path.getsize(path) <= 0:
                self.logger.warning(f"Target {cont_name} file is empty: {path}")
                return None

            # Go to last read position
            file.seek(self.cont_output_files[cont_pid]["position"])

            # Skip header
            if self.cont_output_files[cont_pid]["position"] == 0:
                next(file)

            lines = file.readlines()
            if len(lines) == 0:
                self.logger.warning(f"There aren't new lines to process for target {cont_name}")
                return None
            self.cont_output_files[cont_pid]["position"] = file.tell()

        return lines

    def process_lines(self, lines, cont_name):
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
            if data["timestamp"] < self.start_timestamp:
                continue
            bulk_data.append(data)
        return bulk_data

    def process_container(self, container):
        cont_pid = container["pid"]
        cont_name = container["name"]
        cont_output = self.get_container_output_file(cont_name, cont_pid)

        # If file is not yet accessible, skip
        if not os.path.isfile(cont_output) or not os.access(cont_output, os.R_OK):
            self.logger.warning(f"Couldn't access file from target {cont_name}: {cont_output}")
            return

        # Read target output
        lines = self.read_container_output(cont_output, cont_name, cont_pid)
        if not lines:
            return

        self.__add_iter_info(lines)

        # Gather data from target output
        bulk_data = self.process_lines(lines, cont_name)
        if len(bulk_data) > 0:
            try:
                agg_data = self.aggregate_data(bulk_data, cont_name)
                self.opentsdb_handler.send_data(agg_data)
            except Exception as e:
                self.logger.error("Error sending {0} data to OpenTSDB: {1}".format(cont_name, e))

    def send_power(self):
        # Create log files and set logger
        self.__init_logging_config()

        # Set start timestamp
        self.__set_start_timestamp()

        # Set Ansible information from config files
        self.__set_ansible_info()

        # Set OpenTSDB handler
        self.opentsdb_handler = OpenTSDBHandler(self.ansible_info['opentsdb_addr'], self.ansible_info['opentsdb_port'])

        # Read SmartWatts output and get targets
        while True:
            try:
                # Reset iteration information about processed targets and lines
                self.__reset_iter_info()

                # Process current containers
                t_start = time.perf_counter_ns()
                for container in self.apptainer_handler.get_remote_running_containers_list(self.ansible_info['nodes']):
                    self.process_container(container)
                t_stop = time.perf_counter_ns()
                self.delay = (t_stop - t_start) / 1e9

                # Print iteration information about processed targets and lines
                if self.verbose:
                    self.print_iter_info()

                # Avoids negative sleep times when there is a high delay
                self.adjust_sleep_time()

                time.sleep(self.sampling_frequency - self.delay)

            except Exception as e:
                self.logger.error(f"Unexpected error: {str(e)}")


if __name__ == "__main__":

    if len(sys.argv) < 4:
        raise Exception("Missing some arguments: power_sender.py [-v]"
                        "<SINGULARITY_COMMAND_ALIAS> <SMARTWATTS_OUTPUT> <SAMPLING_FREQUENCY>")

    if sys.argv[1] == "-v":
        verbose = True
        singularity_command_alias = sys.argv[2]
        smartwatts_output = sys.argv[3]
        sampling_frequency = int(sys.argv[4])
    else:
        verbose = False
        singularity_command_alias = sys.argv[1]
        smartwatts_output = sys.argv[2]
        sampling_frequency = int(sys.argv[3])

    try:
        power_sender = PowerSender(verbose, singularity_command_alias, smartwatts_output, sampling_frequency)
        power_sender.send_power()
    except Exception as e:
        raise Exception(f"Error while trying to create PowerSender instance: {str(e)}")

