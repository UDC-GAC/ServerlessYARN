import os
import sys
import json
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

OPENTSDB_URL = "http://127.0.0.1:4242/api/query"

CONTAINER_METRICS = ["proc.cpu.user", "structure.energy.usage"]
APPLICATION_METRICS = ["structure.cpu.current", "structure.energy.max"]

RESOURCE_METRICS = {
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
    "structure.energy.max": "Power Budget (W)",
    "proc.cpu.user": "CPU Usage (%)",
    "structure.cpu.current": "CPU Max (%)"
}

VALUES_TO_FIND_EXP = {
    "serverless_fixed_value": 70,
    "serverless_dynamic_value": 1593,
    "serverless_static_model": 1701,
    "serverless_dynamic_model": 60
}


def create_dir(d):
    os.makedirs(d, exist_ok=True)


def remove_file(f):
    if os.path.exists(f):
        os.remove(f)


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
            start_time_adjusted = start_time #- timedelta(seconds=10)
            stop_time_adjusted = stop_time #+ timedelta(seconds=10)
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


def get_opentsdb_data(metric, containers, start, end, aggregator="zimsum", downsample="5s-avg"):
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
    for container in containers:
        data[container] = {}
        for metric in metrics:
            opentsdb_data = get_opentsdb_data(metric, [container], start, end)

            if opentsdb_data and any(d['dps'] for d in opentsdb_data):
                data[container][metric] = opentsdb_data
            else:
                print(f"No values found for metric {metric} and container {container}")

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
    for container in data:
        for metric, values in data[container].items():
            for ts in values:
                dps = ts['dps']
                for timestamp, value in dps.items():
                    rows.append({
                        'container': container,
                        'metric': metric,
                        'timestamp': timestamp,
                        'elapsed_seconds': pd.to_numeric(timestamp) - start_time,
                        'value': value
                    })

    return pd.DataFrame(rows, columns=['container', 'metric', 'timestamp', 'elapsed_seconds', 'value'])


def plot_experiment_by_app(app_name, containers, exp_name, exp_df, out_dir):
    plt.figure(figsize=(10, 5))
    ax = plt.gca()
    max_plot_value = exp_df['value'].max()

    for metric in RESOURCE_METRICS["all"]:
        filtered_df = exp_df.loc[exp_df['metric'] == metric]
        if metric in CONTAINER_METRICS:
            for container in containers:
                filtered_df = filtered_df.loc[filtered_df['container'] == container]
                plt.plot(filtered_df['elapsed_seconds'], filtered_df['value'], label=f"{LABELS[metric]} - {container}", color=COLORS[metric])
        elif metric in APPLICATION_METRICS:
            filtered_df = filtered_df.groupby(['container', 'elapsed_seconds'], as_index=False).sum()  # TODO: Check if we have to aggregate by sum or avg
            plt.plot(filtered_df['elapsed_seconds'], filtered_df['value'], label=f"{LABELS[metric]}", color=COLORS[metric])

        #if metric == "structure.cpu.current":
        #print_points_between_seconds(exp_name, df, 350, 400)

    plt.xlabel('Execution time (s)', fontsize=12)
    plt.ylabel("CPU Metrics", fontsize=12)
    ax.set_ylim([0, max_plot_value * 1.1])
    plt.grid(True)
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=12, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(f"{out_dir}/{app_name}.png")
    plt.close()


def plot_experiment_by_resource_and_containers(resource, containers, exp_name, exp_df, out_dir):
    plt.figure(figsize=(10, 5))
    ax = plt.gca()
    max_plot_value = 0

    for metric in RESOURCE_METRICS[resource]:
        filtered_df = exp_df.loc[exp_df['metric'] == metric]
        if metric in CONTAINER_METRICS:
            for container in containers:
                filtered_df = filtered_df.loc[filtered_df['container'] == container]
                max_plot_value = max(filtered_df['value'].max(), max_plot_value)
                plt.plot(filtered_df['elapsed_seconds'], filtered_df['value'], label=f"{LABELS[metric]} - {container}", color=COLORS[metric])
        elif metric in APPLICATION_METRICS:
            filtered_df = filtered_df.groupby(['container', 'elapsed_seconds'], as_index=False).sum()  # TODO: Check if we have to aggregate by sum or avg
            max_plot_value = max(filtered_df['value'].max(), max_plot_value)
            plt.plot(filtered_df['elapsed_seconds'], filtered_df['value'], label=f"{LABELS[metric]}", color=COLORS[metric])

    plt.xlabel('Execution time (s)', fontsize=12)
    plt.ylabel("CPU Metrics", fontsize=12)
    ax.set_ylim([0, max_plot_value * 1.1])
    plt.grid(True)
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=12, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(f"{out_dir}/{resource}_{'_'.join(containers)}.png")
    plt.close()


def plot_experiment_by_resource_and_container(resource, container, exp_name, exp_df, out_dir):
    plt.figure(figsize=(10, 5))
    ax = plt.gca()
    max_plot_value = 0
    for metric in RESOURCE_METRICS[resource]:
        filtered_df = exp_df.loc[exp_df['metric'] == metric]
        filtered_df = filtered_df.loc[filtered_df['container'] == container]
        max_plot_value = max(filtered_df['value'].max(), max_plot_value)
        plt.plot(filtered_df['elapsed_seconds'], filtered_df['value'], label=f"{LABELS[metric]}", color=COLORS[metric])

    plt.xlabel('Execution time (s)', fontsize=12)
    plt.ylabel("CPU Metrics", fontsize=12)
    ax.set_ylim([0, max_plot_value * 1.1])
    plt.grid(True)
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=12, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(f"{out_dir}/{resource}_{container}.png")
    plt.close()


def write_experiment_results(exp_name, exp_df, results_file):
    cpu_limit_df = exp_df.loc[exp_df['metric'] == "structure.cpu.current"]
    power_df = exp_df.loc[exp_df['metric'] == "structure.energy.usage"]
    execution_time = exp_df['elapsed_seconds'].max()
    avg_power = power_df['value'].mean()
    results = {
        "Execution time (s)": execution_time,
        "Minimum CPU limit (%)": cpu_limit_df['value'].min(),
        "Average power consumption (W)": avg_power,
        "Average power * Execution time (J)": avg_power * execution_time,
        "Total energy checksum (J)": power_df['value'].sum() * 5
    }

    with open(results_file, "a") as f:
        for name, value in results.items():
            f.write(f"{name}: {value}\n")
            print(f"[{exp_name}] {name}: {value}")

    return results


def write_latex(results_df, out_dir):
    # Configurable parameters
    include_borders = False
    caption = "Experiments"
    label = "tab:experiments"

    # Pre-processing
    # Avoid errors with percentage and underscore symbols
    columns = [col.replace('%', '\\%').replace('_', '\\_') for col in results_df.columns]
    # Set all columns centered (c) and include borders (|) if specified
    column_format = "|".join(["c" for _ in range(len(columns))])
    if include_borders:
        column_format = "|" + column_format + "|"

    # Get LaTeX from DataFrame
    latex_str = results_df.to_latex(index=False,
                                    float_format="%.2f",
                                    header=columns,
                                    column_format=column_format,
                                    label=label,
                                    caption=caption)

    # Post-processing
    # Top-rule: Upper border of the table
    latex_str = latex_str.replace("\\toprule", "\\hline")
    # Mid-rule: Between the headers and the values
    latex_str = latex_str.replace("\\midrule", "\\hline")
    # Bottom-rule: Lower border of the table
    latex_str = latex_str.replace("\\bottomrule", "\\hline" if include_borders else "\\_")
    # Avoid errors with percentage and underscore symbols
    latex_str = latex_str.replace('%', '\\%').replace('_', '\\%')

    # Write latex to .tex file
    with open(f"{out_dir}/global_stats.tex", "w") as f:
        f.write(latex_str)


def write_global_results(results_dict, out_dir):
    results_df = pd.DataFrame.from_dict(results_dict, orient='index').reset_index(names="Experiment")

    # Export the results to many different formats
    write_latex(results_df, out_dir)
    results_df.to_markdown(f"{out_dir}/global_stats.md", index=False)
    results_df.to_csv(f"{out_dir}/global_stats.csv", index=False)
    results_df.to_excel(f"{out_dir}/global_stats.xlsx", index=False)
    results_df.to_html(f"{out_dir}/global_stats.html", index=False)
    results_df.to_json(f"{out_dir}/global_stats.json")


if __name__ == "__main__":

    if len(sys.argv) != 5:
        print("Usage: python get-metrics-opentsdb.py <app-name> <experiments-log-file> <containers-file> <results-directory>")
        sys.exit(1)

    app_name = str(sys.argv[1])
    experiments_dates = read_experiment_times(sys.argv[2])
    experiment_containers_map = map_containers_to_experiments(sys.argv[3], experiments_dates)
    results_dir = sys.argv[4]
    create_dir(results_dir)
    global_results = {}
    print(experiment_containers_map)
    for experiment_name in experiments_dates:

        print(experiment_name.upper().replace("_", " "))

        exp_results_dir = f"{results_dir}/{experiment_name}"
        exp_results_file = f"{exp_results_dir}/stats"
        create_dir(exp_results_dir)
        remove_file(exp_results_file)

        # Get experiment dates
        start_time = int(experiments_dates[experiment_name]["start"].timestamp())
        end_time = int(experiments_dates[experiment_name]["stop"].timestamp())


        # Gather data for these period
        containers = experiment_containers_map[experiment_name]
        data_dict = get_experiment_data(RESOURCE_METRICS["all"], containers, start_time, end_time)
        experiment_df = create_experiment_df(data_dict)
        #df_pivoted = experiment_df.pivot(index='timestamp', columns='metric', values='value').join(experiment_df.set_index('timestamp')[['container', 'elapsed_seconds']])

        # Get experiment plots

        # Plot with all resources and all containers
        plot_experiment_by_app(app_name, containers, experiment_name, experiment_df, exp_results_dir)

        # Separated plot for each resource and container
        single_resources = list(filter(lambda x: x != "all", RESOURCE_METRICS.keys()))
        for resource in single_resources:
            for container in containers:
                plot_experiment_by_resource_and_container(resource, container, experiment_name, experiment_df, exp_results_dir)

        # Write experiment results
        #
        # if experiment_name in VALUES_TO_FIND_EXP:
        #     first_found_point_with_value(experiment_name, data_dict, VALUES_TO_FIND_EXP[experiment_name])
        #
        global_results[experiment_name] = write_experiment_results(experiment_name, experiment_df, exp_results_file)

    write_global_results(global_results, results_dir)

