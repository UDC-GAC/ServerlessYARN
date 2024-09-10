import sys
import requests
import json
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta

OPENTSDB_URL = "http://127.0.0.1:4242/api/query"
METRICS = ["proc.cpu.user", "structure.energy.usage", "structure.cpu.current", "structure.energy.max"]
#METRICS = ["structure.energy.usage", "structure.energy.max"]
HOSTS = ["compute-2-2-cont0"]
TAGS = {
    "structure.energy.usage": {"host": "|".join(HOSTS)},
    "structure.energy.max": {"structure": "|".join(HOSTS)},
    "proc.cpu.user": {"host": "|".join(HOSTS)},
    "structure.cpu.current": {"structure": "|".join(HOSTS)}
}
COLORS = {
    "structure.energy.usage": "#ffc500",
    "structure.energy.max": "#dc0000",
    "proc.cpu.user": "#1f77b4",
    "structure.cpu.current": "#a300dc"
}
VALUES_TO_FIND_EXP = {
    "serverless_fixed_value": 70,
    "serverless_dynamic_value": 1593,
    "serverless_static_model": 1701,
    "serverless_dynamic_model": 60
}


def read_experiment_times(file_path):
    experiments_dates = {}
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for i in range(0, len(lines), 2):
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


def get_opentsdb_data(metric, start, end, aggregator="sum", downsample="5s-avg"):
    query = {
        "start": start,
        "end": end,
        "queries": [
            {
                "metric": metric,
                "aggregator": aggregator,
                "downsample": downsample,
                "tags": TAGS[metric]
            }
        ]
    }
    response = requests.post(OPENTSDB_URL, data=json.dumps(query))

    return response.json()


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


def plot_experiment(exp_name, data, img_dir):
    plt.figure(figsize=(10, 5))
    ax = plt.gca()

    for metric, values in data.items():
        for ts in values:
            dps = ts['dps']
            df = pd.DataFrame(list(dps.items()), columns=['timestamp', 'value'])
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['elapsed_seconds'] = (df['timestamp'] - start_time)
            plt.plot(df['elapsed_seconds'], df['value'], label=f"{metric}", color=COLORS[metric])
            if metric == "structure.cpu.current":
                print_points_between_seconds(exp_name, df, 350, 400)


    plt.xlabel('Execution time (s)')
    plt.ylabel('CPU usage (%) / Power (W)')
    ax.set_ylim([0, 250])
    plt.grid(True)
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=12, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(f"{img_dir}/{exp_name}_only_power.png")
    plt.show()


def sum_total_energy(exp_name, data):
    total_df = pd.DataFrame()
    total_energy = 0
    for metric, values in data.items():
        if metric == "structure.energy.usage":
            for ts in values:
                dps = ts['dps']
                df = pd.DataFrame(list(dps.items()), columns=['timestamp', 'value'])
                df['energy'] = df['value'] * 5  # Sampling frequency
                total_energy += df['energy'].sum()
                total_df = pd.concat([total_df, df])
    print(f"Total energy for experiment {exp_name}: {total_energy} J")
    print(f"Average power consumption for experiment {exp_name}: {total_df['value'].mean()} W")


if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Usage: python get_metrics_opentsdb.py <experiments-log-file> <img-directory>")
        sys.exit(1)

    experiments_dates = read_experiment_times(sys.argv[1])
    img_dir = sys.argv[2]

    for experiment_name in experiments_dates:
        start_str = experiments_dates[experiment_name]["start"].strftime("%Y-%m-%d_%H-%M-%S")
        end_str = experiments_dates[experiment_name]["stop"].strftime("%Y-%m-%d_%H-%M-%S")
        start_time = int(experiments_dates[experiment_name]["start"].timestamp())
        end_time = int(experiments_dates[experiment_name]["stop"].timestamp())

        # Gather data for these dates
        data_dict = {}
        for metric in METRICS:
            data = get_opentsdb_data(metric, start_time, end_time)
            data_dict[metric] = data
        print(f"Plotting experiment {experiment_name} executed between {start_str} and {end_str}. "
              f"Execution time: {experiments_dates[experiment_name]['execution_time'].total_seconds()}")
        # Plot all metrics together
        plot_experiment(experiment_name, data_dict, img_dir)

        if experiment_name in VALUES_TO_FIND_EXP:
            first_found_point_with_value(experiment_name, data_dict, VALUES_TO_FIND_EXP[experiment_name])

        sum_total_energy(experiment_name, data_dict)
