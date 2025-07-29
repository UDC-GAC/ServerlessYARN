import os
import sys
import platform
import pandas as pd
from datetime import timedelta

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
Experiments profiler needs the path to a results directory containing subdirectories for each experiment. Each
subdirectory must contain:
  * Guardian log (guardian.log)
  * Scaler log (scaler.log)
  * File with the list of containers executed for this experiment (containers)
  * One directory per executed container named <container-name>-output containing:
     ** App log file named results.log with format:
        [yyyy-mm-dd hh:mm:ss+zzzz] ...
        [yyyy-mm-dd hh:mm:ss+zzzz] ...
        Being the dates corresponding to the start and end of the app execution, respectively.
"""


class ExperimentsProfiler:

    def __init__(self, app_name, exp_root_dir, plot_config_file, dynamic_pbs):
        self.app_name = app_name
        self.exp_root_dir = exp_root_dir
        self.plot_config_file = plot_config_file
        self.experiments_offset = 20
        self.dynamic_power_budgeting = dynamic_pbs
        self.parser = LogsParser()
        self.writer = ResultsWriter()
        self.plotter = ExperimentsPlotter(self.app_name, plot_config_file)

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
    def get_experiment_containers(exp_results_dir):
        containers_file = os.path.join(exp_results_dir, "containers")
        with open(containers_file, 'r') as f:
            return [line.strip() for line in f if line.strip()]

    @staticmethod
    def search_convergence_point(rescalings, df, offset):
        power_budget = int(utils.get_df_col_avg(utils.filter_df_by_metric(df, "structure.energy.max"), 'value'))
        cpu_limit_df = utils.filter_df_by_metric(df, "structure.cpu.current")
        timestamps = sorted(rescalings.keys())
        needed_scalings = 0
        for timestamp in timestamps:
            # Check scaling is valid
            if 'avg_power' in rescalings[timestamp] and rescalings[timestamp]['elapsed_seconds'] > 0: # and rescalings[timestamp]['amount'] != 0:
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

    @staticmethod
    def get_app_log_files(base_dir):
        # Search "results.log" files inside directories that contain "output" in their names
        log_paths = []
        for name in os.listdir(base_dir):
            if "output" in name and os.path.isdir(os.path.join(base_dir, name)):
                log_file = os.path.join(base_dir, name, "results.log")
                if os.path.isfile(log_file):
                    log_paths.append(log_file)
        return log_paths

    def create_experiment_times_dict(self, start_app, end_app):
        if start_app and end_app:
            start_plot = start_app - timedelta(seconds=self.experiments_offset)
            end_plot = end_app + timedelta(seconds=self.experiments_offset)
            return {
                "start_plot": start_plot,                           # Start of the plot
                "end_plot": end_plot,                               # End of the plot
                "start_app": start_app,                             # Start of the application execution
                "end_app": end_app,                                 # End of the application execution
                "start_plot_s": 0,                                  # Start of the plot (in seconds)
                "end_plot_s": (end_plot - start_plot).seconds,      # End of the plot (in seconds)
                "start_app_s": (start_app - start_plot).seconds,    # Start of the application execution (in seconds)
                "end_app_s": (end_app - start_plot).seconds         # End of the application execution (in seconds)
            }
        return None

    def get_experiment_rescalings(self, guardian_file, experiment_times):
        # Plot start + App start
        experiment_rescalings = {
            experiment_times["start_plot"]: {
                "ts_str": experiment_times["start_plot"].strftime("%Y-%m-%d %H:%M:%S%z"),
                "elapsed_seconds": experiment_times["start_plot_s"],
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
                    timestamp, line_info = self.parser.search_pattern(pattern_name, line, experiment_times["start_plot"])
                    # If pattern is matched we add the extracted info from line and don't check other patterns
                    if timestamp and line_info:
                        # If scaling has been made before the application has finished
                        if timestamp < experiment_times["end_plot"]:
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
        experiment_rescalings[experiment_times["end_plot"]] = {
            "ts_str": experiment_times["end_plot"].strftime("%Y-%m-%d %H:%M:%S%z"),
            "elapsed_seconds": experiment_times["end_plot_s"],
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
                        "elapsed_seconds": (timestamp - experiment_times["start_plot"]).seconds
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
        global_results = {}
        with os.scandir(self.exp_root_dir) as entries:
            experiment_names = [entry.name for entry in entries if entry.is_dir()]

        for experiment_name in experiment_names:
            print(experiment_name.upper().replace("_", " "))
            exp_results_dir = f"{self.exp_root_dir}/{experiment_name}"
            exp_data_file = f'{exp_results_dir}/{experiment_name}-data.csv'
            guardian_file = f"{exp_results_dir}/guardian.log"
            containers = self.get_experiment_containers(exp_results_dir)

            # Get experiment dates from application logs (more accurate than experiments log file)
            app_log_files = self.get_app_log_files(exp_results_dir)
            start_app, end_app = self.parser.get_times_from_app_logs(app_log_files)

            # Create dictionary with useful time info for this experiment
            experiment_times = self.create_experiment_times_dict(start_app, end_app)
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
                data_dict = self.get_experiment_metrics(RESOURCE_METRICS["all"], containers,
                                                        experiment_times["start_plot"], experiment_times["end_plot"])
                experiment_df = self.create_df_from_metrics(data_dict, experiment_times["start_plot"])
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

        self.writer.set_output_dir(self.exp_root_dir)
        self.writer.write_global_results(global_results)


if __name__ == "__main__":

    if len(sys.argv) < 5:
        print(f"Usage: python {sys.argv[0]} <app-name> <experiments-root-directory> <plot-config-file> <dynamic-pbs>")
        sys.exit(1)

    app_name = str(sys.argv[1])
    exp_root_dir = str(sys.argv[2])
    plot_config_file = str(sys.argv[3])
    dynamic_pbs = (int(sys.argv[4]) == 1)

    profiler = ExperimentsProfiler(app_name, exp_root_dir, plot_config_file, dynamic_pbs)
    profiler.profile()
