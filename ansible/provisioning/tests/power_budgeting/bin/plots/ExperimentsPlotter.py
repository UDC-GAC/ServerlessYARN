import os
import hashlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from copy import deepcopy

CONTAINER_METRICS = ["proc.cpu.user", "structure.energy.usage"]
APPLICATION_METRICS = ["structure.cpu.current", "structure.energy.max"]

DEFAULT_COLORS = {
    "structure.energy.usage": "#ffc500",
    "structure.energy.max": "#dc0000",
    "proc.cpu.user": "#1f77b4",
    "structure.cpu.current": "#a300dc"
}

DEFAULT_LABELS = {
    "structure.energy.usage": "Power Usage (W)",
    "structure.energy.max": "Power Budget (W)",
    "proc.cpu.user": "CPU Usage (%)",
    "structure.cpu.current": "CPU Max (%)"
}

DEFAULT_LIMITS = {
    "structure.energy.usage": 220,
    "structure.energy.max": 220,
    "proc.cpu.user": 6400,
    "structure.cpu.current": 6400
}


class ExperimentsPlotter:

    def __init__(self, output_dir=None):
        self._output_dir = output_dir
        self._colors = deepcopy(DEFAULT_COLORS)
        self._labels = deepcopy(DEFAULT_LABELS)
        self._limits = deepcopy(DEFAULT_LIMITS)

    @staticmethod
    def set_value(d, key, value):
        if not d:
            d = {}
        d[key] = value

    @staticmethod
    def get_resource_from_metric(metric):
        parts = metric.split(".")
        try:
            return parts[1]
        except IndexError:
            print(f"Can't get resource from metric {metric}")
        return None

    @staticmethod
    def set_plot_basic_config(ax):
        plt.grid(True)

    @staticmethod
    def set_plot_labels(ax, xlabel, ylabel):
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)

    @staticmethod
    def set_plot_xlim(ax, xlim, perc_offset=1.0):
        ax.set_xlim(xmin=0, xmax=(xlim * perc_offset))

    @staticmethod
    def set_plot_ylim(ax, ylim, perc_offset=1.0):
        ax.set_ylim([0, ylim * perc_offset])

    @staticmethod
    def set_legend(ax):
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=12, framealpha=0.9)

    @staticmethod
    def plot_experiment_rescalings(rescalings):
        timestamps = list(rescalings.keys())
        offset = 0.00001

        x_points = []
        y_points = []
        for start, end in zip(timestamps, timestamps[1:]):
            seconds_start = rescalings[start]['elapsed_seconds']
            seconds_end = rescalings[end]['elapsed_seconds']
            x_points.extend([seconds_start, seconds_end - offset])
            y_points.extend([rescalings[start]['avg_power'], rescalings[start]['avg_power']])

        plt.plot(x_points, y_points, linestyle=':', label=f"Avg rescaling power", color="black")

    def get_output_dir(self):
        return self._output_dir

    def get_color(self, metric):
        return self._colors.get(metric, "#000000")

    def get_label(self, metric):
        return self._labels.get(metric, "")

    def get_limit(self, metric):
        return self._limits.get(metric, 0)

    def set_output_dir(self, d):
        if os.path.isdir(d) and os.path.exists(d):
            self._output_dir = d

    def set_color(self, metric, color):
        self.set_value(self._colors, metric, color)

    def set_label(self, metric, label):
        self.set_value(self._labels, metric, label)

    def set_limit(self, metric, limit):
        self.set_value(self._limits, metric, limit)

    def get_line_label(self, metric, container=None):
        label = self.get_label(metric)
        if container:
            return f"{label} - {container}"
        return label

    def get_line_color(self, metric, container=None):
        metric_color = self.get_color(metric)
        if not container:
            return metric_color

        # Generate a consistent color variation for the container
        hash_value = int(hashlib.md5(container.encode()).hexdigest(), 16)  # Hash container name
        base_rgb = mcolors.to_rgb(metric_color)  # Convert hex to RGB
        variation = (hash_value % 256) / 256  # Generate a variation factor between 0 and 1

        # Adjust the brightness of the metric color based on the variation factor
        adjusted_rgb = tuple(min(1, max(0, c + variation * 0.5 - 0.25)) for c in base_rgb)

        return mcolors.to_hex(adjusted_rgb)  # Convert RGB back to hex

    def get_max_y_value(self, data, metrics):
        max_y = None

        # First we try to get max y value from data
        if data:
            try:
                combined_df = pd.concat(data)
                max_y = combined_df['value'].max()
            except Exception as e:
                print(f"An error has occured trying to get max y value from data: {str(e)}. Provided data: {data}")

        # If no data or bad data is provided we get the maximum default value of all the processed metrics
        if not max_y or np.isnan(max_y) or np.isinf(max_y):
            max_y = max(self.get_limit(metric) for metric in metrics)

        return max_y

    def set_line_plot(self, ax, df, metric, container=None):
        x = df["elapsed_seconds"]
        y = df["value"]
        label = self.get_line_label(metric, container)
        color = self.get_line_color(metric, container)
        plt.plot(x, y, label=label, color=color)
        # linestyle and marker could also be customizable
        # ax.scatter(x[::50], y[::50], s=20, color="black", marker=marker, zorder=3, edgecolors=color, linewidths=0.2)

    @staticmethod
    def set_vline_plot(ax, point, label):
        ax.axvline(x=point, color='black', linestyle='--', label=label)

    def save_plot(self, filename, format='png'):
        path = f'{self._output_dir}/{filename}.{format}'
        plt.tight_layout()
        plt.savefig(path, bbox_inches='tight')

    def plot_container_metrics(self, metrics, container, exp_df, exp_rescalings, exp_times):
        plt.figure(figsize=(10, 5))
        ax = plt.gca()

        processed_dfs = []
        processed_resources = set()
        for metric in metrics:
            filtered_df = exp_df[(exp_df['metric'] == metric) & (exp_df['container'] == container)]
            processed_dfs.append(filtered_df)
            processed_resources.add(self.get_resource_from_metric(metric))
            self.set_line_plot(ax, filtered_df, metric)

        if "structure.energy.usage" in metrics and exp_rescalings:
            self.plot_experiment_rescalings(exp_rescalings)

        # Add vertical lines when app starts and finishes
        self.set_vline_plot(ax, exp_times["start_app_s"], "Start app")
        self.set_vline_plot(ax, exp_times["end_app_s"], "End app")

        # Get max y value found in plotted data
        ylim = self.get_max_y_value(processed_dfs, metrics)

        # Configure and save plot
        self.set_plot_basic_config(ax)
        self.set_plot_xlim(ax, exp_times["end_s"])
        self.set_plot_ylim(ax, ylim, 1.1)
        self.set_plot_labels(ax, "Execution time (s)", "CPU Metrics")
        self.set_legend(ax)
        self.save_plot(f"{'_'.join(list(processed_resources))}_{container}")

        plt.close()

    # TODO: Merge with plot_container_metrics
    def plot_application_metrics(self, app_name, containers, metrics, exp_df, exp_times):
        plt.figure(figsize=(10, 5))
        ax = plt.gca()

        processed_dfs = []
        for metric in metrics:
            filtered_df = exp_df.loc[exp_df['metric'] == metric]
            for container in containers:
                cont_df = filtered_df.loc[filtered_df['container'] == container]
                processed_dfs.append(cont_df)
                self.set_line_plot(ax, cont_df, metric, container)

        # Add vertical lines when app starts and finishes
        self.set_vline_plot(ax, exp_times["start_app_s"], "Start app")
        self.set_vline_plot(ax, exp_times["end_app_s"], "End app")

        # Get max y value found in plotted data
        ylim = self.get_max_y_value(processed_dfs, metrics)

        # Configure and save plot
        self.set_plot_basic_config(ax)
        self.set_plot_xlim(ax, exp_times["end_s"])
        self.set_plot_ylim(ax, ylim, 1.1)
        self.set_plot_labels(ax, "Execution time (s)", "CPU Metrics")
        self.set_legend(ax)
        self.save_plot(app_name)

        plt.close()


