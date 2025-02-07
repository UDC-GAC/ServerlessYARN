import sys
import pandas as pd

from utils import file_exists, get_opentsdb_data
from LogsParser import LogsParser
from ResultsWriter import ResultsWriter
from ExperimentsPlotter import ExperimentsPlotter

OPENTSDB_URL = "http://127.0.0.1:4242/api/query"

RESOURCE_METRICS = {
    "all": ["proc.cpu.user", "structure.energy.usage", "structure.cpu.current", "structure.energy.max"],
    "cpu": ["proc.cpu.user", "structure.cpu.current"],
    "energy": ["structure.energy.usage", "structure.energy.max"]
}


class ExperimentsProfiler:

    def __init__(self, app_name, experiments_log_file, containers_file, results_dir, dynamic_power_budgeting=False):
        self.app_name = app_name
        self.experiments_log_file = experiments_log_file
        self.containers_file = containers_file
        self.results_dir = results_dir
        self.app_type = app_name.split('_')[0]  # (e.g., npb_1cont_1thread -> npb)
        self.experiments_group = results_dir.split("/")[-1].strip()  # (e.g.,./out/results_npb_1cont_1thread/min -> min)
        self.dynamic_power_budgeting = dynamic_power_budgeting
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
                opentsdb_data = get_opentsdb_data(OPENTSDB_URL, metric, [container], start_timestamp, end_timestamp)

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
        if not file_exists(csv_file):
            df.to_csv(csv_file)

    @staticmethod
    def create_experiment_times_dict(start, end, start_app, end_app):
        _dict = None
        if start and end and start_app and end_app:
            _dict = {
                "start": start,
                "end": end,
                "start_app": start_app,
                "end_app": end_app,
                "start_s": 0,
                "end_s": (end - start).seconds,
                "start_app_s": (start_app - start).seconds,
                "end_app_s": (end_app - start).seconds
            }
        return _dict

    @staticmethod
    def get_rescalings_average_power(rescalings, df):
        timestamps = sorted(rescalings.keys())
        power_df = df.loc[df['metric'] == "structure.energy.usage"]
        for start, end in zip(timestamps, timestamps[1:]):
            seconds_start = rescalings[start]['elapsed_seconds']
            seconds_end = rescalings[end]['elapsed_seconds']
            filtered_df = power_df.loc[(power_df['elapsed_seconds'] >= seconds_start) &
                                       (power_df['elapsed_seconds'] <= seconds_end)]
            rescalings[start]['avg_power'] = filtered_df['value'].mean()

        return rescalings

    @staticmethod
    def get_average_between_pbs(pbs, df):
        timestamps = sorted(pbs.keys())
        power_df = df.loc[df['metric'] == "structure.energy.usage"]
        for start, end in zip(timestamps, timestamps[1:]):
            seconds_start = pbs[start]['elapsed_seconds']
            seconds_end = pbs[end]['elapsed_seconds']
            filtered_df = power_df.loc[(power_df['elapsed_seconds'] >= seconds_start) &
                                       (power_df['elapsed_seconds'] <= seconds_end)]
            pbs[start]['avg_power'] = filtered_df['value'].mean()

        return pbs

    @staticmethod
    def get_convergence_point(rescalings, df):
        power_budget_df = df.loc[df['metric'] == "structure.energy.max"]
        power_budget = int(power_budget_df['value'].mean())
        cpu_limit_df = df.loc[df['metric'] == "structure.cpu.current"]
        for timestamp in rescalings:
            if 'avg_power' in rescalings[timestamp] and rescalings[timestamp]['elapsed_seconds'] > 0:
                if power_budget * 0.95 < rescalings[timestamp]['avg_power'] < power_budget * 1.05:
                    cpu_limit = cpu_limit_df.loc[cpu_limit_df['elapsed_seconds'] >
                                                 rescalings[timestamp]['elapsed_seconds'] + 5]
                    return {
                        "time": int(rescalings[timestamp]['elapsed_seconds']),
                        "value": rescalings[timestamp]['avg_power'],
                        "cpu_limit": None if cpu_limit.empty else cpu_limit.iloc[0]['value']
                    }
        return None

    def get_app_log_files(self, base_dir, containers):
        return [f"{base_dir}/{c}-{self.app_type}-output/results.log" for c in containers]

    def get_experiment_rescalings(self, guardian_file, experiment_times):
        experiment_rescalings = {
            experiment_times["start"]: {
                "ts_str": experiment_times["start"].strftime("%Y-%m-%d %H:%M:%S%z"),
                "elapsed_seconds": 0,
                "amount": 0
            },
            # Add start app timestamp as a rescaling to compute avg power between this point and the first rescaling
            # This avoids computing average power before first rescaling using biased data not belonging to app execution
            experiment_times["start_app"]: {
                "ts_str": experiment_times["start_app"].strftime("%Y-%m-%d %H:%M:%S%z"),
                "elapsed_seconds": experiment_times["start_app_s"],
                "amount": 0
            }
        }
        with open(guardian_file, "r") as f:
            for line in f.readlines():
                for pattern_name in ["power_budgeting_pattern", "amount_pattern", "adjust_amount_pattern"]:
                    # Check pattern
                    timestamp, line_info = self.parser.search_pattern(pattern_name, line, experiment_times["start"])
                    # If pattern is matched we add the extracted info from line and don't check other patterns
                    if timestamp and line_info:
                        # If rescaling was made before app has started the start_app point is removed from the dict
                        #if timestamp < experiment_times["start_app"] and experiment_times["start_app"] in experiment_rescalings:
                            #del experiment_rescalings[experiment_times["start_app"]]
                        # Ensure the rescaling has not been made after the application has finished
                        if timestamp < experiment_times["end"]:
                            self.parser.update_timestamp_key_dict(experiment_rescalings, timestamp, line_info)
                        break

        # Add end app timestamp to avoid computing last rescaling power with data not corresponding to app execution
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
        pbs = {
            experiment_times["start_app"]: {
                "ts_str": experiment_times["start_app"].strftime("%Y-%m-%d %H:%M:%S%z"),
                "elapsed_seconds": experiment_times["start_app_s"],
                "power_budget": 0
            }
        }
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

            # Get experiment rescaling timestamps and average power
            experiment_rescalings = self.get_experiment_rescalings(guardian_file, experiment_times)
            experiment_rescalings = self.get_rescalings_average_power(experiment_rescalings, experiment_df)
            convergence_point = self.get_convergence_point(experiment_rescalings, experiment_df)
            #print(experiment_rescalings)

            power_budgets = None
            power_budgets_file = None
            if self.dynamic_power_budgeting:
                power_budgets_file = f"{exp_results_dir}/power_budgets.log"
                power_budgets = self.read_pbs_timestamps(power_budgets_file, experiment_times)
                power_budgets = self.get_average_between_pbs(power_budgets, experiment_df)
                print(power_budgets)

            # Set output directory to store plots
            self.plotter.set_output_dir(exp_results_dir)

            # Plot application metrics (all containers + all metrics)
            self.plotter.plot_application_metrics(experiment_name, containers, RESOURCE_METRICS["all"], experiment_df,
                                                  experiment_times, experiment_rescalings, convergence_point)

            # Create separated plots for each resource and container
            single_resources = list(filter(lambda x: x != "all", RESOURCE_METRICS.keys()))
            for resource in single_resources:
                for container in containers:
                    if power_budgets:
                        self.plotter.plot_application_metrics(experiment_name, [container], RESOURCE_METRICS[resource],
                                                              experiment_df, experiment_times, power_budgets,
                                                              convergence_point)
                    else:
                        self.plotter.plot_application_metrics(experiment_name, [container], RESOURCE_METRICS[resource],
                                                              experiment_df, experiment_times, experiment_rescalings,
                                                              convergence_point)

            self.writer.set_output_dir(exp_results_dir)
            global_results[experiment_name] = self.writer.write_experiment_results(experiment_name, experiment_df,
                                                                                  experiment_times, convergence_point)

        self.writer.set_output_dir(self.results_dir)
        self.writer.write_global_results(global_results)


if __name__ == "__main__":

    if len(sys.argv) < 5:
        print("Usage: python get-metrics-opentsdb.py <app-name> <experiments-log-file> <containers-file> "
              "<results-directory> [dynamic_budgets]")
        sys.exit(1)

    app_name = str(sys.argv[1])
    experiments_log_file = sys.argv[2]
    containers_file = sys.argv[3]
    results_dir = sys.argv[4]
    dynamic_power_budgeting = True if len(sys.argv) >= 6 and sys.argv[5] == "dynamic_budgets" else False

    profiler = ExperimentsProfiler(app_name, experiments_log_file, containers_file, results_dir, dynamic_power_budgeting)
    profiler.profile()
