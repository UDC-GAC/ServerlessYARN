import sys
import pandas as pd

from utils import create_dir, get_opentsdb_data
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

    def __init__(self, app_name, experiments_log_file, containers_file, results_dir):
        self.parser = LogsParser()
        self.writer = ResultsWriter()
        self.plotter = ExperimentsPlotter()
        self.app_name = app_name
        self.app_type = app_name.split('_')[0]  # (e.g., npb_1cont_1thread -> npb)
        self.experiments_log_file = experiments_log_file
        self.containers_file = containers_file
        self.results_dir = results_dir

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
    def create_experiment_times_dict(start, end, start_app, end_app):
        return {
            "start": start,
            "end": end,
            "start_app": start_app,
            "end_app": end_app,
            "start_s": 0,
            "end_s": (end - start).seconds,
            "start_app_s": (start_app - start).seconds,
            "end_app_s": (end_app - start).seconds
        }

    def get_app_log_files(self, base_dir, containers):
        return [f"{base_dir}/{c}-{self.app_type}-output/results.log" for c in containers]

    def get_experiment_rescalings(self, guardian_file, start_time, end_time):
        experiment_rescalings = {
            start_time: {"ts_str": start_time.strftime("%Y-%m-%d %H:%M:%S%z"), "elapsed_seconds": 0, "amount": 0}
        }
        with open(guardian_file, "r") as f:
            for line in f.readlines():
                for pattern_name in ["power_budgeting_pattern", "amount_pattern", "adjust_amount_pattern"]:
                    # Check pattern
                    timestamp, line_info = self.parser.search_pattern(pattern_name, line, start_time)

                    # If pattern is matched we add the extracted info from line and don't check other patterns
                    if timestamp and line_info:
                        # Ensure the rescaling has not been made after the application has finished
                        if timestamp < end_time:
                            self.parser.update_timestamp_key_dict(experiment_rescalings, timestamp, line_info)
                        break
        experiment_rescalings[end_time] = {
            "ts_str": end_time.strftime("%Y-%m-%d %H:%M:%S%z"), "elapsed_seconds": (end_time - start_time).seconds, "amount": 0
        }
        return experiment_rescalings

    @staticmethod
    def get_rescalings_average_power(rescalings, df):
        timestamps = list(rescalings.keys())
        power_df = df.loc[df['metric'] == "structure.energy.usage"]
        for start, end in zip(timestamps, timestamps[1:]):
            seconds_start = rescalings[start]['elapsed_seconds']
            seconds_end = rescalings[end]['elapsed_seconds']
            filtered_df = power_df.loc[(power_df['elapsed_seconds'] >= seconds_start) &
                                       (power_df['elapsed_seconds'] <= seconds_end)]
            rescalings[start]['avg_power'] = filtered_df['value'].mean()

        return rescalings

    def profile(self):
        experiments_dates = self.parser.get_experiments_timestamps(experiments_log_file)
        experiment_containers_map = self.parser.map_containers_to_experiments(containers_file, experiments_dates)

        global_results = {}
        for experiment_name in experiments_dates:
            print(experiment_name.upper().replace("_", " "))
            exp_results_dir = f"{results_dir}/{experiment_name}"
            guardian_file = f"{exp_results_dir}/guardian.log"
            containers = experiment_containers_map[experiment_name]

            start_time, end_time = experiments_dates[experiment_name]["start"], experiments_dates[experiment_name]["stop"]

            # Get experiment dates from application logs (more accurate than experiments log file)
            app_log_files = self.get_app_log_files(exp_results_dir, containers)
            start_app, end_app = self.parser.get_times_from_app_logs(app_log_files)

            # Create dictionary with useful time info for this experiment
            experiment_times = self.create_experiment_times_dict(start_time, end_time, start_app, end_app)

            # Gather metrics for these period and create DataFrame
            data_dict = self.get_experiment_metrics(RESOURCE_METRICS["all"], containers, start_time, end_time)
            experiment_df = self.create_df_from_metrics(data_dict, start_time)

            # Get experiment rescaling timestamps and average power
            experiment_rescalings = self.get_experiment_rescalings(guardian_file, start_time, end_time)
            experiment_rescalings = self.get_rescalings_average_power(experiment_rescalings, experiment_df)

            # Set output directory to store plots
            self.plotter.set_output_dir(exp_results_dir)

            # Plot application metrics (all containers + all metrics)
            self.plotter.plot_application_metrics(app_name, containers, RESOURCE_METRICS["all"],
                                                  experiment_df, experiment_times)

            # Create separated plots for each resource and container
            single_resources = list(filter(lambda x: x != "all", RESOURCE_METRICS.keys()))
            for resource in single_resources:
                for container in containers:
                    self.plotter.plot_container_metrics(RESOURCE_METRICS[resource], container, experiment_df,
                                                        experiment_rescalings, experiment_times)

            self.writer.set_output_dir(exp_results_dir)
            global_results[experiment_name] = self.writer.write_experiment_results(experiment_name, experiment_df,
                                                                                   experiment_times)

        self.writer.set_output_dir(results_dir)
        self.writer.write_global_results(global_results)


if __name__ == "__main__":

    if len(sys.argv) != 5:
        print("Usage: python get-metrics-opentsdb.py <app-name> <experiments-log-file> <containers-file> <results-directory>")
        sys.exit(1)

    app_name = str(sys.argv[1])
    experiments_log_file = sys.argv[2]
    containers_file = sys.argv[3]
    results_dir = sys.argv[4]

    profiler = ExperimentsProfiler(app_name, experiments_log_file, containers_file, results_dir)
    profiler.profile()
