import os
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone

DEFAULT_PATTERNS = {
    "found_structure_pattern": {"value": r"1\sStructures\sto\sprocess,\slaunching\sthreads", "get_amount": False},
    "no_structure_pattern": {"value": r"No\sstructures\sto\sprocess", "get_amount": False},
    "power_budgeting_pattern": {"value": r".*POWER\sBUDGETING.*", "get_amount": False},
    "amount_pattern": {"value": r"amount\s([-+]?\d+)", "get_amount": True},
    "adjust_amount_pattern": {"value": r"has\sbeen\strimmed\sfrom\s([-+]?\d+)\sto\s([-+]?\d+)", "get_amount": True},
    "rescale_event_pattern": {"value": r".*TRIGGERED\sREQUESTS\s\['(EnergyRescaleUp|EnergyRescaleDown)'\].*", "get_amount": False},
}


class LogsParser:

    def __init__(self, dates_fmt="%Y-%m-%d %H:%M:%S%z", patterns=None):
        self.dates_fmt = dates_fmt
        self.patterns = patterns if patterns else deepcopy(DEFAULT_PATTERNS)

    def __get_pattern_item(self, pattern_name, item):
        if pattern_name in self.patterns:
            if item in self.patterns[pattern_name]:
                return self.patterns[pattern_name][item]
            raise KeyError(f"Item {item} doesn't exist in patterns dictionary (patttern_name = {pattern_name})")
        raise KeyError(f"Pattern with name {pattern_name} doesn't exist.")

    def __str_to_dt(self, _str):
        try:
            if _str and len(_str) > 0:
                return datetime.strptime(_str, self.dates_fmt).astimezone(timezone.utc)
        except ValueError:
            print(f"Trying to convert bad string to datetime: {_str}")
        return None

    def __dt_to_str(self, dt):
        try:
            if dt:
                return dt.strftime(self.dates_fmt)
        except Exception as e:
            print(f"Trying to convert bad datetime to string: {dt}. ERROR: {str(e)}")
        return None

    @staticmethod
    def add_offset(ts, offset):
        if ts and offset != 0:
            ts = ts + timedelta(seconds=offset)
        return ts

    def get_experiments_timestamps(self, file, offset=0):
        """ Get experiment start and end timestamps from logs. Optionally, an offset can be added to the start and end
        of the experiments. It expects the format:

            <EXP-NAME> <start|stop> YYYY-MM-DD HH:MM:SS

        Args:
            file (string): File containing the logs

        Returns:
            experiments_timestamps (dict): Dictionary containing the start and end timestamps of each experiment.
        """
        experiments_timestamps = {}
        with open(file, 'r') as f:
            lines = f.readlines()
            total_lines = len(lines) if len(lines) % 2 == 0 else len(lines) - 1

            for i in range(0, total_lines, 2):
                # Get info from logs
                experiment_name = lines[i].split()[0]
                start_time_str = lines[i].split()[2] + " " + lines[i].split()[3]
                stop_time_str = lines[i + 1].split()[2] + " " + lines[i + 1].split()[3]

                # Convert string dates to datetimes
                start_time = self.__str_to_dt(start_time_str)
                stop_time = self.__str_to_dt(stop_time_str)

                # Compute execution time of the experiment
                execution_time = (stop_time - start_time).seconds

                # Add ofset to start and end
                start_time_adjusted = self.add_offset(start_time, -offset)
                stop_time_adjusted = self.add_offset(stop_time, offset)

                # Store in the dictionary
                experiments_timestamps[experiment_name] = {
                    "start": start_time_adjusted,
                    "stop": stop_time_adjusted,
                    "execution_time": execution_time
                }

        return experiments_timestamps

    def map_containers_to_experiments(self, containers_file, experiments_dates):
        """ Read key-value pairs from a file that provide the correspondence between a container and the moment it was
        executed. Then, map each container to the experiment that includes that moment between its start and end.

        Args:
            containers_file (string): File with key-value pairs <TIMESTAMP> <CONTAINER_NAME>.
            experiments_dates (dict): Dictionary containing the start and the end of each experiment.

        Returns:
            experiments_timestamps (dict): Dictionary containing the start and end timestamps of each experiment.
        """
        experiment_containers_map = {}
        for experiment_name in experiments_dates:
            experiment_containers_map[experiment_name] = []

        with open(containers_file, 'r') as file:
            for line in file.readlines():
                parts = line.split()
                timestamp_str = parts[0] + " " + parts[1]
                container = parts[2]
                timestamp = self.__str_to_dt(timestamp_str)
                for experiment_name in experiments_dates:
                    if experiments_dates[experiment_name]["start"] < timestamp < experiments_dates[experiment_name]["stop"]:
                        if container not in experiment_containers_map[experiment_name]:
                            experiment_containers_map[experiment_name].append(container)

        return experiment_containers_map

    def read_timestamp_from_log_line(self, line):
        """Reads timestamps from lines belonging to log files written in a specific format. Line format:

            [YYYY-MM-DD HH:MM:SS] <Some info> ...
            [YYYY-MM-DD HH:MM:SS] <Another info> ...
            ...

        Args:
            line (string): Line to process

        Returns:
            timestamp_str, timestamp (tuple<string,datetime>): Timestamp in string and datetime format
        """
        timestamp = None
        timestamp_str = None
        parts = line.split()

        # There should be 2 fields at least (YYYY-MM-DD and HH:MM:SS)
        if len(parts) < 2:
            print(f"Couldn't get timestamps from line (not enough fields): {line}")
            return timestamp_str, timestamp

        try:
            yyyy_mm_dd = parts[0][1:]
            hh_mm_ss = parts[1][0:13]
            timestamp_str = "{0} {1}".format(yyyy_mm_dd, hh_mm_ss)
            timestamp = self.__str_to_dt(timestamp_str)
        except IndexError as e:
            print(f"Couldn't get timestamps from line: {line}. IndexError trying to get date from first [1:] "
                  f"or second split [0:13]. ERROR: {str(e)}")
        except Exception as e:
            print(f"Couldn't get timestamps from line: {line}. ERROR: {str(e)}")

        return timestamp_str, timestamp

    def read_timestamp_from_log_file(self, file):
        start_time = None
        end_time = None
        if os.path.isfile(file) and os.path.exists(file):
            with open(file, "r") as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    _, start_time = self.read_timestamp_from_log_line(lines[0])
                    _, end_time = self.read_timestamp_from_log_line(lines[-1])
                else:
                    print(f"Trying to read log file having less than 2 lines. At least, it must exist one line with "
                          f"the start and another with the end. File content: {lines}")

        return start_time, end_time

    def get_times_from_app_logs(self, app_log_files, offset=0):
        """ Get experiment start and end timestamps from application logs. Optionally, an offset can be added to the
        start and end of the experiments. Application logs must have the format:

            [YYYY-MM-DD HH:MM:SS] ...

        Args:
            app_log_files (list): List of files with the application logs.
            offset (int): Offset to substract from the start and add to the end (optional).

        Returns:
            earlier_start_time, newer_end_time (tuple): Timestamp of the first container to start and the last to end
        """
        earlier_start_time = None
        newer_end_time = None

        # Get the first container to start and the last to end
        for file in app_log_files:
            start_time, end_time = self.read_timestamp_from_log_file(file)
            if start_time:
                if not earlier_start_time or start_time < earlier_start_time:
                    earlier_start_time = start_time
            if end_time:
                if not newer_end_time or end_time > newer_end_time:
                    newer_end_time = end_time
        earlier_start_time = self.add_offset(earlier_start_time, -offset)
        newer_end_time = self.add_offset(newer_end_time, offset)

        return earlier_start_time, newer_end_time

    def _get_timestamp_with_offset(self, d, timestamp, offset):
        new_timestamp = None
        timestamp_before = self.add_offset(timestamp, -offset)
        timestamp_after = self.add_offset(timestamp, offset)

        # Check if timestamp has changed between patterns of the same rescaling
        if timestamp not in d:
            if timestamp_before in d:
                new_timestamp = timestamp_before
            if timestamp_after in d:
                new_timestamp = timestamp_after

        return new_timestamp

    def update_timestamp_key_dict(self, d, timestamp, value, offset=1):
        """ Update dict using timestamps as keys, taking into account that this timestamps could have an offset.

        Args:
            d (dict): Dictionary to update, if it is None it is created
            timestamp (datetime): Timestamp used as key
            value (Any): Value to store in the dict using the corresponding key
            offset (int): Offset in seconds to consider timestamps as the same key (i.e., all timestamps included in
                          timestamp +- offset are interpreted as the same key)

        Returns:
            None
        """
        if not d:
            print("Trying to update a non existent dictionary")
            return

        new_timestamp = self._get_timestamp_with_offset(d, timestamp, offset)

        if new_timestamp:
            d[new_timestamp] = value
        else:
            d[timestamp] = value

    def remove_timestamp_key_dict(self, d, timestamp, offset=1):
        """ Remove item from dict using timestamps as keys, taking into account that this timestamps could have an offset.

        Args:
            d (dict): Dictionary to update, if it is None it is created
            timestamp (datetime): Timestamp used as key to remove
            offset (int): Offset in seconds to consider timestamps as the same key (i.e., all timestamps included in
                          timestamp +- offset are interpreted as the same key)

        Returns:
            None
        """
        if not d:
            print("Trying to update a non existent dictionary")
            return

        if timestamp in d:
            del d[timestamp]

        new_timestamp = self._get_timestamp_with_offset(d, timestamp, offset)
        if new_timestamp:
            del d[new_timestamp]
        else:
            print(f"Trying to remove non existent key from dictionary: {timestamp}")

    def search_pattern(self, pattern_name, line, start_time):
        timestamp = None
        line_info = None
        amount = 0
        pattern = self.__get_pattern_item(pattern_name, "value")
        if re.search(pattern, line):
            # Get timestamp from line and convert to dt
            timestamp_str, timestamp = self.read_timestamp_from_log_line(line)

            if timestamp_str and timestamp:
                # Get time elapsed since application has started
                elapsed_time = (timestamp - start_time).seconds

                # Update amount if proper pattern is used
                if self.__get_pattern_item(pattern_name, "get_amount"):
                    amount = int(line.split()[-1])

                line_info = {"ts_str": timestamp_str, "elapsed_seconds": elapsed_time, "amount": amount}
            else:
                print("Pattern was found but timestamp was not found or there is a  bad timestamp in the log file line")

        return timestamp, line_info

    # def get_start_time_from_guardian(self, guardian_file, pattern_name="found_structure_pattern"):
    #     t = None
    #     with open(guardian_file, "r") as f:
    #         for line in f.readlines():
    #             if re.search(self.__get_pattern_item(pattern_name, "value"), line):
    #                 t = self.read_timestamp_from_log_line(line)[1]
    #                 break
    #     return t
    #
    # def get_end_time_from_guardian(self, guardian_file, t_start, pattern_name="no_structure_pattern"):
    #     t = None
    #     with open(guardian_file, "r") as f:
    #         for line in f.readlines():
    #             if re.search(self.__get_pattern_item(pattern_name, "value"), line):
    #                 t_aux = self.read_timestamp_from_log_line(line)[1]
    #                 if t_aux > t_start:
    #                     t = t_aux
    #                     break
    #     return t
