import sys
import json
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

OPENTSDB_URL = "http://127.0.0.1:4242/api/query"

METRICS = {
    "all": ["proc.cpu.user", "structure.energy.usage", "structure.cpu.current", "structure.energy.max"],
    "cpu": ["proc.cpu.user", "structure.cpu.current"],
    "energy": ["structure.energy.usage", "structure.energy.max"]
}

LIMITS = {
    "cpu": 3300,
    "energy": 200,
}

COLORS = {
    "structure.energy.usage": "#ffc500",
    "structure.energy.max": "#dc0000",
    "proc.cpu.user": "#1f77b4",
    "structure.cpu.current": "#a300dc"
}

LABELS = {
    "structure.energy.usage": "Power Usage (W)",
    "structure.energy.max": "Power Budget(W)",
    "proc.cpu.user": "CPU Usage (%)",
    "structure.cpu.current": "CPU Max (%)"
}

VALUES_TO_FIND_EXP = {
    "serverless_fixed_value": 70,
    "serverless_dynamic_value": 1593,
    "serverless_static_model": 1701,
    "serverless_dynamic_model": 60
}
# TODO: Manage plots for multiple containers (maybe associate metrics with containers in create_experiment_df)


def read_experiment_times(file_path):
    experiments_dates = {}
    with open(file_path, 'r') as file:
        lines = file.readlines()
        total_lines = len(lines) if len(lines) % 2 == 0 else len(lines) - 1

        for i in range(0, total_lines, 2):
            experiment_name = lines[i].split()[0]
            start_time_str = lines[i].split()[2] + " " + lines[i].split()[3]
            stop_time_str = lines[i + 1].split()[2] + " " + lines[i + 1].split()[3]
            start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S%z')
            stop_time = datetime.strptime(stop_time_str, '%Y-%m-%d %H:%M:%S%z')

            # Add a little margin to start and end
            start_time_adjusted = start_time - timedelta(seconds=10)
            stop_time_adjusted = stop_time + timedelta(seconds=10)
            execution_time = stop_time - start_time
            #stop_time_adjusted = start_time + timedelta(seconds=1000)

            # Store in the dictionary
            experiments_dates[experiment_name] = {
                "start": start_time_adjusted,
                "stop": stop_time_adjusted,
                "execution_time": execution_time
            }

    return experiments_dates


def map_containers_to_experiments(containers_file, experiments_dates):
    experiment_containers_map = {}
    for experiment_name in experiments_dates:
        experiment_containers_map[experiment_name] = []

    with open(containers_file, 'r') as file:
        for line in file.readlines():
            parts = line.split()
            timestamp_str = parts[0] + " " + parts[1]
            container = parts[2]
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S%z')
            for experiment_name in experiments_dates:
                if experiments_dates[experiment_name]["start"] < timestamp < experiments_dates[experiment_name]["stop"]:
                    if container not in experiment_containers_map[experiment_name]:
                        experiment_containers_map[experiment_name].append(container)

    return experiment_containers_map


def get_tags(metric, containers):
    if metric in ["structure.energy.usage", "proc.cpu.user"]:
        field_name = "host"
    elif metric in ["structure.energy.max", "structure.cpu.current"]:
        field_name = "structure"
    else:
        raise Exception(f"Metric {metric} is not supported. Failed while fetching a tag for this metric")

    return {field_name: "|".join(containers)}


def get_opentsdb_data(metric, containers, start, end, aggregator="sum", downsample="5s-avg"):
    query = {
        "start": start,
        "end": end,
        "queries": [
            {
                "metric": metric,
                "aggregator": aggregator,
                "downsample": downsample,
                "tags": get_tags(metric, containers)
            }
        ]
    }
    response = requests.post(OPENTSDB_URL, data=json.dumps(query))

    return response.json()


def get_experiment_data(metrics, containers, start, end):
    data = {}
    for metric in metrics:
        opentsdb_data = get_opentsdb_data(metric, containers, start, end)
        if opentsdb_data and any(d['dps'] for d in opentsdb_data):
            data[metric] = opentsdb_data
        else:
            print(f"No values found for metric {metric} and containers: {containers}")

    return data


def print_points_between_seconds(exp_name, df, min, max, num_points=5):
    for row in df.iterrows():
        if min < row[1]['elapsed_seconds'] < max and num_points > 0:
            print(f"CPU Limit found for {exp_name}: {row[1]['value']} ({row[1]['elapsed_seconds']}s)")
            num_points -= 1


def first_found_point_with_value(exp_name, data, value, min_time=0):
    first_point = float('1e+30')
    for metric, values in data.items():
        if metric == "structure.cpu.current":
            for ts in values:
                df = pd.DataFrame(list(ts['dps'].items()), columns=['timestamp', 'value'])
                df['elapsed_seconds'] = (pd.to_numeric(df['timestamp']) - start_time)
                for row in df.iterrows():
                    if row[1]['value'] == value and min_time < row[1]['elapsed_seconds'] < first_point:
                        first_point = row[1]['elapsed_seconds']

    print(f"First found point with value {value} for experiment {exp_name}: {first_point}")


def create_experiment_df(data):
    rows = []
    for metric, values in data.items():
        for ts in values:
            dps = ts['dps']
            for timestamp, value in dps.items():
                rows.append({
                    'metric': metric,
                    'timestamp': timestamp,
                    'elapsed_seconds': pd.to_numeric(timestamp) - start_time,
                    'value': value
                })

    return pd.DataFrame(rows, columns=['metric', 'timestamp', 'elapsed_seconds', 'value'])


def plot_experiment(exp_name, exp_df, img_dir, resource):
    plt.figure(figsize=(10, 5))
    ax = plt.gca()
    max_plot_value = exp_df['value'].max()

    for metric in METRICS[resource]:
        filtered_df = exp_df.loc[exp_df['metric'] == metric]
        plt.plot(filtered_df['elapsed_seconds'], filtered_df['value'], label=f"{metric}", color=COLORS[metric])
        #if metric == "structure.cpu.current":
            #print_points_between_seconds(exp_name, df, 350, 400)

    plt.xlabel('Execution time (s)', fontsize=12)
    plt.ylabel("CPU Metrics", fontsize=12)
    ax.set_ylim([0, max_plot_value * 1.1])
    plt.grid(True)
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=12, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(f"{img_dir}/{exp_name}_{resource}.png")
    plt.show()


def sum_total_energy(exp_name, exp_df):
    power_df = exp_df.loc[exp_df['metric'] == "structure.energy.usage"]

    avg_power = power_df['value'].mean()
    total_energy = avg_power * power_df['elapsed_seconds'].max()
    total_energy_checksum = power_df['value'].sum() * 5

    print(f"[{exp_name}] Average power consumption: {avg_power} W")
    print(f"[{exp_name}] Total energy (avg power * elapsed time): {total_energy} J")
    print(f"[{exp_name}] Total energy checksum: {total_energy_checksum} J")


if __name__ == "__main__":

    if len(sys.argv) != 4:
        print("Usage: python get-metrics-opentsdb.py <experiments-log-file> <containers-file> <img-directory>")
        sys.exit(1)

    experiments_dates = read_experiment_times(sys.argv[1])
    experiment_containers_map = map_containers_to_experiments(sys.argv[2], experiments_dates)
    img_dir = sys.argv[3]
    print(experiment_containers_map)
    for experiment_name in experiments_dates:
        start_str = experiments_dates[experiment_name]["start"].strftime("%Y-%m-%d_%H-%M-%S")
        end_str = experiments_dates[experiment_name]["stop"].strftime("%Y-%m-%d_%H-%M-%S")
        start_time = int(experiments_dates[experiment_name]["start"].timestamp())
        end_time = int(experiments_dates[experiment_name]["stop"].timestamp())

        # Gather data for these period
        containers = experiment_containers_map[experiment_name]
        data_dict = get_experiment_data(METRICS["all"], containers, start_time, end_time)

        print(f"[{experiment_name}] Start timestamp: {start_str}")
        print(f"[{experiment_name}] Stop timestamp:  {end_str}")
        print(f"[{experiment_name}] Execution time: {experiments_dates[experiment_name]['execution_time'].total_seconds()}")

        experiment_df = create_experiment_df(data_dict)

        # TODO: Manage to get separated plots for each resource (maybe by container too)
        plot_experiment(experiment_name, experiment_df, img_dir, "all")
        #
        # if experiment_name in VALUES_TO_FIND_EXP:
        #     first_found_point_with_value(experiment_name, data_dict, VALUES_TO_FIND_EXP[experiment_name])
        #
        sum_total_energy(experiment_name, experiment_df)
