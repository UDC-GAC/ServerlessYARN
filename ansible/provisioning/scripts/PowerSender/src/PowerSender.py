import logging.handlers
import os
import sys
import time
import yaml
import logging
import subprocess
import pandas as pd
from threading import Thread

from datetime import datetime, timezone
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager

from src.opentsdb.OpenTSDBHandler import OpenTSDBHandler
from src.utils.MyUtils import MyUtils, IterationLogger

SCRIPT_PATH = os.path.abspath(__file__)
POWER_SENDER_DIR = os.path.dirname(os.path.dirname(SCRIPT_PATH))
PROVISIONING_DIR = os.path.dirname(os.path.dirname(POWER_SENDER_DIR))
ANSIBLE_CONFIG_FILE = "{0}/config/config.yml".format(PROVISIONING_DIR)
ANSIBLE_VARS_FILE = "{0}/vars/main.yml".format(PROVISIONING_DIR)
ANSIBLE_INVENTORY_FILE = "{0}/../ansible.inventory".format(PROVISIONING_DIR)
LOG_DIR = "{0}/log".format(POWER_SENDER_DIR)
LOG_FILE = "{0}/power_sender.log".format(LOG_DIR)
MAX_LOG_SIZE = 10  # Max log file size in MB


class PowerSender:

    def __init__(self, _verbose, _installation_path, _power_meter, _sampling_frequency):
        self.verbose = _verbose

        # Installation path of ServerlessYARN platform
        self.__set_installation_path(_installation_path)

        # Power meter (RAPL or SmartWatts)
        self.__set_power_meter(_power_meter)

        # SmartWatts output directory
        self.__set_smartwatts_output("{0}/smartwatts/output".format(_installation_path))

        # Sampling frequency to read and send data
        self.__set_sampling_frequency(_sampling_frequency)

        # File mapping containers with their PIDs
        self.containers_pid_mapfile = None

        # CPU Sockets
        self.cpu_sockets = None

        # Logger to print information
        self.logger = None

        # Start timestamp to send only data obtained after the start of this program
        self.start_timestamp = None

        # OpenTSDB handler to send data
        self.opentsdb_handler = None

        # Dictionary to store output files and their last read position
        self.cont_output_files = {}

        # Dictionary to store information about the current iteration
        self.iter_logger = IterationLogger()

        # Delay between iterations
        self.delay = 0

    def __set_installation_path(self, path):
        if not (os.path.exists(path) and os.path.isdir(path)):
            raise ValueError("Installation path doesn't exist or it isn't a directory: {0}".format(str(path)))
        self.installation_path = path

    def __set_power_meter(self, name):
        if not (isinstance(name, str) and name in ["rapl", "smartwatts"]):
            raise ValueError("Trying to set a bad power meter: {0}".format(str(name)))
        self.power_meter = name

    def __set_smartwatts_output(self, path):
        if not (os.path.exists(path) and os.path.isdir(path)):
            raise ValueError("Smartwatts output doesn't exist or it isn't a directory: {0}".format(str(path)))
        self.smartwatts_output = path

    def __set_sampling_frequency(self, n):
        if not (isinstance(n, int) and n > 0):
            raise ValueError("Trying to set a bad sampling frequency value: {0}".format(str(n)))
        self.sampling_frequency = n

    def __set_logging_config(self):
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

    def __set_containers_pid_mapfile(self, mapfile):
        if os.path.isfile(mapfile) and os.access(mapfile, os.R_OK):
            self.containers_pid_mapfile = mapfile
        else:
            self.logger.warning("Trying to set a non-accesible file as container-PID mapfile: {0}".format(mapfile))

    def __set_opentsdb_handler(self, address, port):
        if not isinstance(address, str):
            raise ValueError("OpenTSDB address must be a string")

        if not isinstance(port, int) or not (0 <= port <= 65535):
            raise ValueError("Port must be an integer between 0 and 65535")
        self.opentsdb_handler = OpenTSDBHandler(address, port)

    def __set_start_timestamp(self):
        self.start_timestamp = datetime.now(timezone.utc)
        self.logger.info("Start time: {0}".format(self.start_timestamp))

    def __set_cpu_sockets(self):
        try:
            result = subprocess.run(["lscpu"], stdout=subprocess.PIPE, text=True)
            for line in result.stdout.splitlines():
                if "Socket(s):" in line:
                    self.cpu_sockets = int(line.split(":")[1].strip())
        except Exception as e:
            self.logger.error("Error getting number of sockets: {0}".format(str(e)))
            exit(1)

        if not self.cpu_sockets:
            self.logger.error("Information about number of sockets couldn\'t be found")
            exit(1)

    @staticmethod
    def get_ansible_info():
        with open(ANSIBLE_CONFIG_FILE, "r") as f:
            ansible_config = yaml.load(f, Loader=yaml.FullLoader)
        with open(ANSIBLE_VARS_FILE, "r") as f:
            ansible_vars = yaml.load(f, Loader=yaml.FullLoader)
        loader = DataLoader()
        ansible_inventory = InventoryManager(loader=loader, sources=ANSIBLE_INVENTORY_FILE)

        return {
            "opentsdb_addr": ansible_config['server_ip'],
            "opentsdb_port": ansible_config['opentsdb_port'],
            "nodes": ansible_inventory.get_groups_dict()['nodes'],
            "containers_pid_mapfile": ansible_vars['containers_pid_mapping_file']
        }

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
        # Aggregate data by cpu (mean) and timestamp (sum): All dps from the same CPU are averaged and all averaged dps
        # belonging to the same timestamp are summed up
        agg_data = pd.DataFrame(bulk_data).groupby(['timestamp', 'cpu']).agg({'value': 'mean'}).reset_index()\
                                          .groupby('timestamp').agg({'value': 'sum'}).reset_index()

        # TODO: Set a buffer to take into account more metrics when computing the outliers
        if power_meter == "smartwatts":
            agg_data = PowerSender.remove_outliers(agg_data, 'value')

        # If RAPL is used, the power overhead of HWPC Sensor should be taken into account
        # Nevertheless, last experiments shown that this overhead is negligible
        # hwpc_sensor_power = 5 if power_meter == "rapl" else 0

        # Format data into a dict to dump into a JSON
        return [
            {"metric": "structure.energy.usage",
             "tags": {"host": cont_name},
             "timestamp": int(row['timestamp'].timestamp() * 1000),
             "value": row['value']  # - hwpc_sensor_power
             }
            for _, row in agg_data .iterrows()
        ]

    def print_iter_info(self):
        self.logger.info("Processed {0} targets and {1} lines causing a delay of {2} seconds"
                         .format(self.iter_logger.get_targets(), self.iter_logger.get_lines(), self.delay))

    def adjust_sleep_time(self):
        if self.delay > self.sampling_frequency:
            self.logger.warning("High delay ({0}) causing negative sleep times. Waiting until the next {1}s cycle"
                                .format(self.delay, self.sampling_frequency))
            self.delay = self.delay % self.sampling_frequency

    def get_container_output_file(self, name, pid):
        # If container is not registered, initialize it
        if pid not in self.cont_output_files:
            target = "rapl" if self.power_meter == "rapl" else "apptainer-{0}".format(pid)
            target_file = "{0}/sensor-{1}/PowerReport.csv".format(self.smartwatts_output, target)

            self.logger.info("Found new target with name {0} and pid {1}. Registered.".format(name, pid))
            self.cont_output_files[pid] = {
                "path": target_file,
                "position": os.path.getsize(target_file)
            }

        return self.cont_output_files[pid]["path"]

    def read_container_output(self, path, cont_name, cont_pid):
        with open(path, 'r', encoding='utf-8') as file:
            # If file is empty, skip
            if os.path.getsize(path) <= 0:
                self.logger.warning("Target {0} file is empty: {1}".format(cont_name, path))
                return None

            # Go to last read position
            file.seek(self.cont_output_files[cont_pid]["position"])

            # Skip header
            if self.cont_output_files[cont_pid]["position"] == 0:
                next(file)

            lines = file.readlines()
            if len(lines) == 0:
                self.logger.warning("There aren't new lines to process for target {0}".format(cont_name))
                return None

            # Update last position and save last line length in bytes
            self.cont_output_files[cont_pid]["position"] = file.tell()
            self.cont_output_files[cont_pid]["last_line_bytes"] = len(lines[-1].encode('utf-8'))

        return lines

    def update_position_to_previous_line(self, cont_pid):
        last_line_bytes = self.cont_output_files[cont_pid]["last_line_bytes"]
        if last_line_bytes > 0:
            self.cont_output_files[cont_pid]["position"] -= (last_line_bytes + 1)
            self.cont_output_files[cont_pid]["last_line_bytes"] = -1
        else:
            self.logger.warning("No information about the last line bytes when trying to find previous line")

    def preprocess_data(self, bulk_data, cont_pid):
        # Check for missing CPU values in any timestamp
        check_list = [True for _ in range(self.cpu_sockets)]
        preprocessed_data = []
        last_dp_was_ignored = False
        for ts in bulk_data:
            ts_check_list = check_list.copy()
            for dp in bulk_data[ts]:
                # Although it is counter-intuitive, we mark the CPUs found as False, to check if
                # there are any CPUs not found with any() (as we check if there exists any True value)
                ts_check_list[dp["cpu"]] = False

            # If there is missing data for any CPU we ignore this data point
            if not any(ts_check_list):
                last_dp_was_ignored = False
                for dp in bulk_data[ts]:
                    preprocessed_data.append({
                        "timestamp": ts,
                        "value": dp["value"],
                        "cpu": dp["cpu"]
                    })
            else:
                last_dp_was_ignored = True

        # If we ignored the last dp we try to process it in the next iteration
        if last_dp_was_ignored:
            self.update_position_to_previous_line(cont_pid)

        return preprocessed_data

    def process_lines(self, lines, cont_name):
        bulk_data = {}
        for line in lines:
            # line example: <timestamp> <sensor> <target> <value> ...
            fields = line.strip().split(',')
            num_fields = len(fields)
            if num_fields < 4:
                self.logger.error("Missing some fields in SmartWatts output for target {0} "
                                  "({1} out of 4 expected fields)".format(cont_name, num_fields))

            # SmartWatts hour = UTC+00:00 - offset(Europe/Madrid) (UTC+02:00 summer schedule or UTC+01:00 winter one)
            # We read timestamp as Europe/Madrid to sum exactly this offset and then we mark the timestamp as UTC
            # This way OpenTSDB interprets the real UTC+00:00 (Smartwatts + offset(Europe/Madrid))
            timestamp = datetime.fromtimestamp(int(fields[0]) / 1000).replace(tzinfo=timezone.utc)
            data = {
                "value": float(fields[3]),
                "cpu": int(fields[4])
            }
            # Only dps obtained after the start of this program are sent
            if timestamp < self.start_timestamp:
                continue
            if timestamp not in bulk_data:
                bulk_data[timestamp] = []

            bulk_data[timestamp].append(data)

        return bulk_data

    def process_container(self, container):
        cont_pid = container["pid"]
        cont_name = container["name"]
        cont_output = self.get_container_output_file(cont_name, cont_pid)

        # If file is not yet accessible, skip
        if not os.path.isfile(cont_output) or not os.access(cont_output, os.R_OK):
            self.logger.warning("Couldn't access file from target {0}: {1}".format(cont_name, cont_output))
            return

        # Read target output
        lines = self.read_container_output(cont_output, cont_name, cont_pid)
        if not lines:
            return

        # Log the amount of lines processed for this target
        self.iter_logger.add_info(lines)

        # Gather data from target output
        bulk_data = self.process_lines(lines, cont_name)
        preprocessed_data = self.preprocess_data(bulk_data, cont_pid)
        if len(preprocessed_data) > 0:
            try:
                agg_data = self.aggregate_data(preprocessed_data, cont_name)
                self.opentsdb_handler.send_data(agg_data)
            except Exception as e:
                self.logger.error("Error sending {0} data to OpenTSDB: {1}".format(cont_name, str(e)))

    def get_running_containers(self):
        running_containers = []

        if not os.path.isfile(self.containers_pid_mapfile) or not os.access(self.containers_pid_mapfile, os.R_OK):
            self.logger.warning("Couldn't access containers mapping file: {0}".format(self.containers_pid_mapfile))
            self.logger.warning("No container will be processed in this iteration")
            return running_containers

        with open(self.containers_pid_mapfile, 'r') as file:
            # If file is empty, skip
            if os.path.getsize(self.containers_pid_mapfile) <= 0:
                self.logger.warning("Containers mapping file is empty: {0}".format(self.containers_pid_mapfile))
                self.logger.warning("No container will be processed in this iteration")
                return running_containers

            for line in file.readlines():
                try:
                    name, pid = line.strip().split(":")
                    running_containers.append({"name": name, "pid": pid})
                except Exception as e:
                    self.logger.warning("Invalid line in containers mapping file: {0} ({1})".format(line, str(e)))

        return running_containers

    def send_power(self):

        # Get Ansible information from config files
        ansible_info = self.get_ansible_info()

        # Create log files and set logger
        self.__set_logging_config()

        # Get number of sockets in this CPU
        # TODO: Take into account that server hosting PowerSender could have a different CPU than monitored servers
        self.__set_cpu_sockets()

        # Set start timestamp
        self.__set_start_timestamp()

        # Set containers PID mapping file
        self.__set_containers_pid_mapfile(
            ansible_info['containers_pid_mapfile'].replace("{{ installation_path }}", self.installation_path))

        # Set OpenTSDB handler
        self.__set_opentsdb_handler(ansible_info['opentsdb_addr'], ansible_info['opentsdb_port'])

        # Read SmartWatts output and get targets
        while True:
            try:
                # Reset iteration information about processed targets and lines
                self.iter_logger.reset()

                # Process current containers in separated threads
                t_start = time.perf_counter_ns()
                threads = []
                for container in self.get_running_containers():
                    thread = Thread(name="process_{0}".format(container["name"]), target=self.process_container,
                                    args=(container,))
                    thread.start()
                    threads.append(thread)

                for t in threads:
                    t.join()
                t_stop = time.perf_counter_ns()
                self.delay = (t_stop - t_start) / 1e9

                # Print iteration information about processed targets and lines
                if self.verbose:
                    self.print_iter_info()

                # Avoids negative sleep times when there is a high delay
                self.adjust_sleep_time()

                time.sleep(self.sampling_frequency - self.delay)

            except Exception as e:
                self.logger.error("Unexpected error: {0}".format(str(e)))
                time.sleep(self.sampling_frequency)


if __name__ == "__main__":

    if len(sys.argv) < 3:
        raise Exception("Missing some arguments: power_sender.py [-v] <INSTALLATION_PATH> <POWER_METER> <SAMPLING_FREQUENCY>")

    if sys.argv[1] == "-v":
        verbose = True
        installation_path = sys.argv[2]
        power_meter = sys.argv[3]
        sampling_frequency = int(sys.argv[4])
    else:
        verbose = False
        installation_path = sys.argv[1]
        power_meter = sys.argv[2]
        sampling_frequency = int(sys.argv[3])

    try:
        power_sender = PowerSender(verbose, installation_path, power_meter, sampling_frequency)
        power_sender.send_power()
    except Exception as e:
        raise Exception("Error while trying to create PowerSender instance: {0}".format(str(e)))

