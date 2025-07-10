import sys
import platform
import pandas as pd

import utils.utils as utils
from logs.LogsParser import LogsParser
from writer.ResultsWriter import ResultsWriter
from plots.ExperimentsPlotter import ExperimentsPlotter

OPENTSDB_URL = "http://127.0.0.1:4242/api/query"

RESOURCE_METRICS = {
    "all": ["proc.cpu.user", "structure.energy.usage", "structure.cpu.current", "structure.energy.max"],
    "cpu": ["proc.cpu.user", "structure.cpu.current"],
    "energy": ["structure.energy.usage", "structure.energy.max"]
}

DIRECTORY_SEP = "\\" if platform.system() == "Windows" else "/"

"""
Experiments profiler needs:

* An experiments file log file with format:

<experiment-name> start yyyy-mm-dd hh:mm:ss+zzzz
<experiment-name> stop  yyyy-mm-dd hh:mm:ss+zzzz

* A containers log file with format:

<container-name> yyyy-mm-dd hh:mm:ss+zzzz

If a container corresponds to a specific experiment, its date must correspond to a point in time between experiment start and end.

* Results directory containing subdirectories for each experiment included in experiments log file. Each subdirectory must 
  contain:
  ** Guardian log (guardian.log)
  ** Scaler log (scaler.log)
  ** One directory per executed container named <container-name>-<app-name>-output containing:
     *** App execution log with format:
         [yyyy-mm-dd hh:mm:ss+zzzz] ...
         [yyyy-mm-dd hh:mm:ss+zzzz] ...
         Being the dates corresponding to the start and end of the app execution, respectively.
"""


class ExperimentsProfiler:

    def __init__(self, app_name, experiments_log_file, containers_file, results_dir):
        self.app_name = app_name
        self.experiments_log_file = experiments_log_file
        self.containers_file = containers_file
        self.results_dir = results_dir
        self.app_type = app_name.split('_')[0]  # (e.g., npb_1cont_1thread -> npb)
        self.experiments_group = results_dir.split(DIRECTORY_SEP)[-1].strip()  # (e.g.,./out/results_npb_1cont_1thread/min -> min)
        self.dynamic_power_budgeting = (self.experiments_group == "dynamic_power_budget")
        self.parser = LogsParser()
        self.writer = ResultsWriter()
        self.plotter = ExperimentsPlotter(self.app_name, self.experiments_group)

    @staticmethod
    def get_experiment_metrics(metrics, containers, start, end):
        data = {}
        start_timestamp, end_timestamp = int(start.timestamp()), int(end.timestamp())
        for container in containers:
            data[container] = {}
            for metric in metrics:
                opentsdb_data = utils.get_opentsdb_data(OPENTSDB_URL, metric, [container], start_timestamp, end_timestamp)

                if opentsdb_data and any(d['dps'] for d in opentsdb_data):
                    data[container][metric] = opentsdb_data
                else:
                    print(f"No values found for metric {metric} and container {container}")

        return data

    @staticmethod
    def create_df_from_metrics(data, start):
        rows = []
        start_timestamp = int(start.timestamp())
        for container in data:
            for metric, values in data[container].items():
                for ts in values:
                    dps = ts['dps']
                    for timestamp, value in dps.items():
                        rows.append({
                            'container': container,
                            'metric': metric,
                            'timestamp': timestamp,
                            'elapsed_seconds': int(timestamp) - start_timestamp,
                            'value': value
                        })
        return pd.DataFrame(rows, columns=['container', 'metric', 'timestamp', 'elapsed_seconds', 'value'])

    @staticmethod
    def save_experiment_df(df, csv_file):
        if not utils.file_exists(csv_file):
            df.to_csv(csv_file)

    @staticmethod
    def create_experiment_times_dict(start, end, start_app, end_app):
        if start and end and start_app and end_app:
            return {
                "start": start,                                 # Start of the plot
                "end": end,                                     # End of the plot
                "start_app": start_app,                         # Start of the application execution
                "end_app": end_app,                             # End of the application execution
                "start_s": 0,                                   # Start of the plot (in seconds)
                "end_s": (end - start).seconds,                 # End of the plot (in seconds)
                "start_app_s": (start_app - start).seconds,     # Start of the application execution (in seconds)
                "end_app_s": (end_app - start).seconds          # End of the application execution (in seconds)
            }
        return None

    @staticmethod
    def search_convergence_point(rescalings, df, offset):
        power_budget = int(utils.get_df_col_avg(utils.filter_df_by_metric(df, "structure.energy.max"), 'value'))
        cpu_limit_df = utils.filter_df_by_metric(df, "structure.cpu.current")
        timestamps = sorted(rescalings.keys())
        needed_scalings = 0
        for timestamp in timestamps:
            # Check scaling is valid
            if 'avg_power' in rescalings[timestamp] and rescalings[timestamp]['elapsed_seconds'] > 0 and rescalings[timestamp]['amount'] != 0:
                needed_scalings += 1
                # Check scaling average power is near the power budget (convergence)
                if utils.value_is_near_limit(rescalings[timestamp]['avg_power'], power_budget, offset):
                    # Return convergence point
                    cpu_limit_df = utils.filter_df_by_period(cpu_limit_df, start=(rescalings[timestamp]['elapsed_seconds'] + 5))
                    return {
                        "time": int(rescalings[timestamp]['elapsed_seconds']),
                        "value": rescalings[timestamp]['avg_power'],
                        "needed_scalings": needed_scalings,
                        "cpu_limit": None if cpu_limit_df.empty else cpu_limit_df.iloc[0]['value']
                    }
        return None

    def get_app_log_files(self, base_dir, containers):
        return [f"{base_dir}/{c}-{self.app_type}-output/results.log" for c in containers]

    def get_experiment_rescalings(self, guardian_file, experiment_times):
        # Plot start + App start
        experiment_rescalings = {
            experiment_times["start"]: {
                "ts_str": experiment_times["start"].strftime("%Y-%m-%d %H:%M:%S%z"),
                "elapsed_seconds": 0,
                "amount": 0
            },
            experiment_times["start_app"]: {
                "ts_str": experiment_times["start_app"].strftime("%Y-%m-%d %H:%M:%S%z"),
                "elapsed_seconds": experiment_times["start_app_s"],
                "amount": 0
            }
        }
        # Search all the performed scalings in Guardian logs
        with open(guardian_file, "r") as f:
            for line in f.readlines():
                for pattern_name in ["amount_pattern", "adjust_amount_pattern"]:
                    # Check pattern
                    timestamp, line_info = self.parser.search_pattern(pattern_name, line, experiment_times["start"])
                    # If pattern is matched we add the extracted info from line and don't check other patterns
                    if timestamp and line_info:
                        # If scaling has been made before the application has finished
                        if timestamp < experiment_times["end"]:
                            # If scaling amount is greater than zero we add/update it
                            if line_info["amount"] != 0:
                                print(f"Line was saved using pattern {pattern_name}: {timestamp}")
                                self.parser.update_timestamp_key_dict(experiment_rescalings, timestamp, line_info)
                            # If the scaling was later trimmed (adjust_amount_pattern) to zero it should be removed
                            elif pattern_name == "adjust_amount_pattern":
                                print(f"Line was removed because it was trimmed to zero: {timestamp}")
                                self.parser.remove_timestamp_key_dict(experiment_rescalings, timestamp)
                        break
        # App end + Plot end
        experiment_rescalings[experiment_times["end_app"]] = {
            "ts_str": experiment_times["end_app"].strftime("%Y-%m-%d %H:%M:%S%z"),
            "elapsed_seconds": experiment_times["end_app_s"],
            "amount": 0
        }
        experiment_rescalings[experiment_times["end"]] = {
            "ts_str": experiment_times["end"].strftime("%Y-%m-%d %H:%M:%S%z"),
            "elapsed_seconds": experiment_times["end_s"],
            "amount": 0
        }
        return experiment_rescalings

    def read_pbs_timestamps(self, file, experiment_times):
        # App start
        pbs = {
            experiment_times["start_app"]: {
                "ts_str": experiment_times["start_app"].strftime("%Y-%m-%d %H:%M:%S%z"),
                "elapsed_seconds": experiment_times["start_app_s"],
                "power_budget": 0
            }
        }
        # The start and end of the power budgets is provided in a file (power_budgets.log)
        with open(file, "r") as f:
            for line in f.readlines():
                try:
                    timestamp_str, timestamp = self.parser.read_timestamp_from_log_line(line)
                    pbs[timestamp] = {
                        "ts_str": timestamp_str,
                        "power_budget": int(line.split()[2]),
                        "elapsed_seconds": (timestamp - experiment_times["start"]).seconds
                    }
                except Exception as e:
                    print(f"Error reading line from power budget file: {file}. Line is: {line}. Error: {str(e)}")
        # App end
        pbs[experiment_times["end_app"]] = {
            "ts_str": experiment_times["end_app"].strftime("%Y-%m-%d %H:%M:%S%z"),
            "elapsed_seconds": experiment_times["end_app_s"],
            "power_budget": 0
        }

        return pbs

    def profile(self):
        experiments_dates = self.parser.get_experiments_timestamps(experiments_log_file)
        experiment_containers_map = self.parser.map_containers_to_experiments(containers_file, experiments_dates)

        global_results = {}
        for experiment_name in experiments_dates:
            print(experiment_name.upper().replace("_", " "))
            exp_results_dir = f"{self.results_dir}/{experiment_name}"
            exp_data_file = f'{exp_results_dir}/{experiment_name}-data.csv'
            guardian_file = f"{exp_results_dir}/guardian.log"
            containers = experiment_containers_map[experiment_name]

            start_time, end_time = experiments_dates[experiment_name]["start"], experiments_dates[experiment_name]["stop"]

            # Get experiment dates from application logs (more accurate than experiments log file)
            app_log_files = self.get_app_log_files(exp_results_dir, containers)
            start_app, end_app = self.parser.get_times_from_app_logs(app_log_files)

            # Create dictionary with useful time info for this experiment
            experiment_times = self.create_experiment_times_dict(start_time, end_time, start_app, end_app)
            if not experiment_times:
                print(f"Experiment times couldn't be retrieved for method {experiment_name}, ignoring...")
                continue

            # First, try getting data from CSV file
            experiment_df = None
            try:
                experiment_df = pd.read_csv(exp_data_file, index_col=0)
            except FileNotFoundError:
                print(f"Getting method {experiment_name} data from OpenTSDB")
            except Exception as e:
                print(f"An error occurred reading experiment {experiment_name} data from file {exp_data_file}: {str(e)}. "
                      f"Getting data from OpenTSDB")

            # If metrics couldn't be retrieved from CSV file they are collected from OpenTSDB
            if experiment_df is None:
                # Gather metrics for these period and create DataFrame
                data_dict = self.get_experiment_metrics(RESOURCE_METRICS["all"], containers, start_time, end_time)
                experiment_df = self.create_df_from_metrics(data_dict, start_time)
                # Save experiment data
                self.save_experiment_df(experiment_df, exp_data_file)
            # If metrics couldn't also be retrieved from OpenTSDB, this experiment is ignored
            if experiment_df is None:
                print(f"Experiment {experiment_name} data couldn't be retrieved neither from the CSV "
                      f"file nor from OpenTSDB. Ignoring...")
                continue

            convergence_point = None
            if self.dynamic_power_budgeting:
                # Get power budgets timestamps and average between PBs
                intervals = self.read_pbs_timestamps(f"{exp_results_dir}/power_budgets.log", experiment_times)
                intervals = utils.compute_avg_per_interval(intervals, experiment_df, "structure.energy.usage")
            else:
                # Get experiment rescaling timestamps and average power
                intervals = self.get_experiment_rescalings(guardian_file, experiment_times)
                intervals = utils.compute_avg_per_interval(intervals, experiment_df, "structure.energy.usage")
                convergence_point = self.search_convergence_point(intervals, experiment_df, 0.05)

            # Print intervals (all the performed scalings or all the power budgets)
            utils.print_dict(intervals)

            # Set output directory to store plots
            self.plotter.set_output_dir(exp_results_dir)

            # Plot application metrics (all containers + all metrics)
            self.plotter.plot_application_metrics(experiment_name, containers, RESOURCE_METRICS["all"], experiment_df,
                                                  experiment_times, intervals, convergence_point)

            # Create separated plots for each resource and container
            single_resources = list(filter(lambda x: x != "all", RESOURCE_METRICS.keys()))
            for resource in single_resources:
                for container in containers:
                    self.plotter.plot_application_metrics(experiment_name, [container], RESOURCE_METRICS[resource],
                                                          experiment_df, experiment_times, intervals, convergence_point)

            # Write experiment results
            self.writer.set_output_dir(exp_results_dir)
            global_results[experiment_name] = self.writer.write_experiment_results(experiment_name, experiment_df,
                                                                                   experiment_times, convergence_point)

        self.writer.set_output_dir(self.results_dir)
        self.writer.write_global_results(global_results)


if __name__ == "__main__":

    if len(sys.argv) < 5:
        print(f"Usage: python {sys.argv[0]} <app-name> <experiments-log-file> <containers-file> <results-directory>")
        sys.exit(1)

    app_name = str(sys.argv[1])
    experiments_log_file = sys.argv[2]
    containers_file = sys.argv[3]
    results_dir = sys.argv[4]

    profiler = ExperimentsProfiler(app_name, experiments_log_file, containers_file, results_dir)
    profiler.profile()
