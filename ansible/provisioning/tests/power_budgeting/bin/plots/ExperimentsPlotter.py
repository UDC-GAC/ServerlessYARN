import os
import hashlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as patches

from copy import deepcopy
from CustomExperimentsPlots import PLOT_PARAMETERS

CONTAINER_METRICS = ["proc.cpu.user", "structure.energy.usage"]
APPLICATION_METRICS = ["structure.cpu.current", "structure.energy.max"]

METRICS_CONFIG = {
    "structure.energy.usage": {
        "axis": 1,
        "color": "#fe802a",
        "label": "Power usage (W)",
        "linestyle": "-",
        "marker": "o",
        "limit": 220
    },
    "structure.energy.max": {
        "axis": 1,
        "color": "#dc0000",
        "label": "Power budget (W)",
        "linestyle": "-",
        "marker": "x",
        "limit": 220
    },
    "proc.cpu.user": {
        "axis": 0,
        "color": "#1f77b4",
        "label": "CPU shares",
        "linestyle": "-",
        "marker": "o",
        "limit": 6400
    },
    "structure.cpu.current": {
        "axis": 0,
        "color": "#a300dc",
        "label": "CPU limit",
        "linestyle": "-",
        "marker": "x",
        "limit": 6400
    }
}


class ExperimentsPlotter:

    def __init__(self, app_name, experiments_group, output_dir=None):
        self._output_dir = output_dir
        self._app_name = app_name
        self._experiments_group = experiments_group
        self.__load_config()
        self._metrics_config = deepcopy(METRICS_CONFIG)

    def __load_config(self):
        self.__config = deepcopy(
            PLOT_PARAMETERS.get(self._app_name, {}).get(self._experiments_group, PLOT_PARAMETERS.get("default", {})))

    @staticmethod
    def __get_resource_from_metric(metric):
        try:
            return metric.split(".")[1].strip()
        except IndexError:
            return None

    @staticmethod
    def __rescalings_can_be_plotted(containers, metrics, exp_rescalings):
        return len(containers) == 1 and len(metrics) == 2 and "structure.energy.usage" in metrics and exp_rescalings

    @staticmethod
    def __get_nearest_limit(n):
        for lim in [100, 200, 400, 800, 1600]:
            if n <= lim:
                return lim
        return 3200

    @staticmethod
    def __custom_color_by_container(color, container=None):
        if not container:
            return color

        # Generate a consistent color variation for the container
        hash_value = int(hashlib.md5(container.encode()).hexdigest(), 16)  # Hash container name
        base_rgb = mcolors.to_rgb(color)  # Convert hex to RGB
        variation = (hash_value % 256) / 256  # Generate a variation factor between 0 and 1

        # Adjust the brightness of the metric color based on the variation factor
        adjusted_rgb = tuple(min(1, max(0, c + variation * 0.5 - 0.25)) for c in base_rgb)

        return mcolors.to_hex(adjusted_rgb)  # Convert RGB back to hex

    def __get_potential_limits(self, max_values):
        if self.__config.get("SEPARATE_AXES", False):
            return self.__get_nearest_limit(max_values["cpu"]) if "cpu" in max_values else None, \
                self.__get_nearest_limit(max_values["energy"]) if "energy" in max_values else None
        else:
            return self.__get_nearest_limit(max_values["all"]), None

    def __set_plot_basic_config(self, axes):
        plt.grid(True)
        axes[0].tick_params(axis='both', labelsize=self.__config.get("DEFAULT_FONTSIZE", 20))
        if self.__config.get("SEPARATE_AXES", False):
            axes[1].tick_params(axis='both', labelsize=self.__config["DEFAULT_FONTSIZE"])

    def __set_plot_labels(self, axes, labels):
        fontsize = self.__config.get("DEFAULT_FONTSIZE", 20)
        if "y2" in labels:
            if self.__config.get("SEPARATE_AXES", False):
                axes[0].set_xlabel(labels["x"], fontsize=fontsize)
                axes[0].set_ylabel(labels["y1"], fontsize=fontsize)
                axes[1].set_ylabel(labels["y2"], fontsize=fontsize)
            else:
                axes[0].set_xlabel(labels["x"], fontsize=fontsize)
                axes[0].set_ylabel(f"{labels['y1']} / {labels['y2']}", fontsize=fontsize)
        else:
            axes[0].set_xlabel(labels["x"], fontsize=fontsize)
            axes[0].set_ylabel(labels['y1'], fontsize=fontsize)

    def __set_plot_limits(self, axes, xlim, ylims):
        if self.__config.get("SEPARATE_AXES", False):
            axes[0].set_xlim(0, self.__config.get("HARD_X_LIMIT", xlim))
            axes[0].set_ylim(0, self.__config.get("HARD_Y_LIMIT", ylims[0]))
            axes[1].set_ylim(0, self.__config.get("HARD_Y_LIMIT_2", ylims[1]))
        else:
            axes[0].set_xlim(0, self.__config.get("HARD_X_LIMIT", xlim))
            axes[0].set_ylim(0, self.__config.get("HARD_Y_LIMIT", ylims[0]))

    @staticmethod
    def __generate_ticks(limit, ticks_frequency):
        # It adds an offset if limit is between one tick and the next
        # Example: limit=107, ticks_frequency=20 -> 107 + (20 - (107 % 20)) % 20 = 107 + 13 % 20 = 120
        #          limit=100, ticks_frequency=20 -> 100 + (20 - (100 % 20)) % 20 = 107 + 20 % 20 = 100
        return np.arange(0, limit + (ticks_frequency - (limit % ticks_frequency)) % ticks_frequency + 1, ticks_frequency)

    def __set_plot_ticks(self, axes, xlim, ylims):
        axes[0].set_xticks(self.__generate_ticks(self.__config.get("HARD_X_LIMIT", xlim), self.__config.get("X_TICKS_FREQUENCY", 20)))
        if self.__config.get("SEPARATE_AXES", False):
            axes[0].set_yticks(self.__generate_ticks(self.__config.get("HARD_Y_LIMIT", ylims[0]), self.__config.get("Y_TICKS_FREQUENCY", 20)))
            axes[1].set_yticks(self.__generate_ticks(self.__config.get("HARD_Y_LIMIT_2", ylims[1]), self.__config.get("Y_TICKS_FREQUENCY_2", 20)))
        else:
            axes[0].set_yticks(self.__generate_ticks(self.__config.get("HARD_Y_LIMIT", ylims[0]), self.__config.get("Y_TICKS_FREQUENCY", 20)))

    def __set_legend(self, ax):
        ax.legend(loc='upper center',
                  bbox_to_anchor=(0.66, 0.60),
                  ncol=2,
                  fontsize=self.__config.get("DEFAULT_FONTSIZE", 20) + 2,
                  markerscale=2,
                  facecolor="lightblue",
                  framealpha=0.75)

    def __configure_plot(self, axes, xlim, ylims, labels):
        self.__set_plot_basic_config(axes)
        self.__set_plot_limits(axes, xlim, ylims)
        self.__set_plot_ticks(axes, xlim, ylims)
        self.__set_plot_labels(axes, labels)
        if self.__config.get("PLOT_LEGEND", False):
            self.__set_legend(axes[0])

    @staticmethod
    def __create_rectangle(left_corner, width, height, color, pattern):
        return patches.Rectangle(
            left_corner, width, height, color=color, alpha=0.2, hatch=pattern, linewidth=0, edgecolor=None)

    def __plot_convergence_point(self, ax, ylim, convergence_point, times):
        fig_ylim = self.__generate_ticks(self.__config.get("HARD_Y_LIMIT", ylim),
                                         self.__config.get("Y_TICKS_FREQUENCY", 20))[-1]
        if convergence_point:
            # Red pattern
            ax.add_patch(self.__create_rectangle(
                (times["start_app_s"], 0), convergence_point["time"] - times["start_app_s"], fig_ylim, "red", "x"))

            # Convergence point
            self.__set_vline_plot(ax, convergence_point["time"], label=None)

            # Green pattern
            ax.add_patch(self.__create_rectangle(
                (convergence_point["time"], 0), times["end_app_s"] - convergence_point["time"], fig_ylim, "green", "o"))
        else:
            # Red pattern
            ax.add_patch(self.__create_rectangle(
                (times["start_app_s"], 0), times["end_app_s"] - times["start_app_s"], fig_ylim, "red", "x"))

    def __set_vline_plot(self, ax, point, label):
        ax.axvline(x=point, color='black', linestyle='--', linewidth=1.5, zorder=-2)
        # Add text on the X axis if provided
        if self.__config["PLOT_APP_LABELS"] and label:
            ylim = ax.get_ylim()[1]
            ax.annotate(label, xy=(point+5, ylim - 10), xytext=(point+5, ylim - 10), fontsize=self.__config["DEFAULT_FONTSIZE"])

    def __get_max_value(self, df, metric):
        max_y = None
        # First we try to get max y value from data
        try:
            max_y = df['value'].max()
        except Exception as e:
            print(f"An error has occured trying to get max y value from data: {str(e)}.")

        # If no data or bad data is provided we get the maximum default value of all the processed metrics
        if not max_y or np.isnan(max_y) or np.isinf(max_y):
            max_y = self.__get_metric_config(metric).get("limit", 0)

        return max_y

    def __get_metric_config(self, metric):
        return self._metrics_config.get(metric, {"color": "#000000", "label": "", "linestyle": "-", "marker": "", "limit": 0})

    def __plot_metric(self, axes, df, metric, container=None):
        config = self.__get_metric_config(metric)
        label = f"{config['label']} - {container}" if container else config['label']

        # If there are various containers assign different colors to each one
        color = self.__custom_color_by_container(config['color'], container)

        # Select appropiate axis if metrics are plotted in separate axes
        ax_index = config['axis'] if self.__config.get("SEPARATE_AXES", False) else 0

        # Plot line
        axes[ax_index].plot(df["elapsed_seconds"], df["value"],
                            label=label,
                            color=color,
                            linestyle=config['linestyle'],
                            marker=config['marker'],
                            markersize=12,
                            markevery=self.__config.get("MARKER_FREQUENCY", None))

    def __generate_plot_name(self, experiment_name, metrics, containers):
        resource = None
        container = None
        if len(metrics) == 2:
            resource = self.__get_resource_from_metric(metrics[0])
        if len(containers) == 1:
            container = containers[0]
        # ATM: Containers are ignored as this is only used for single-container applications
        return experiment_name + (f"_{resource}" if resource else "")  # + (f"_{container}" if container else "")

    def __save_plot(self, filename, format='png'):
        path = f'{self._output_dir}/{filename}.{format}'
        plt.tight_layout()
        plt.savefig(path, bbox_inches='tight')

    @staticmethod
    def plot_experiment_rescalings(ax, rescalings):
        timestamps = sorted(rescalings.keys())
        offset = 0.00001

        x_points = []
        y_points = []
        for start, end in zip(timestamps, timestamps[1:]):
            seconds_start = rescalings[start]['elapsed_seconds']
            seconds_end = rescalings[end]['elapsed_seconds']
            x_points.extend([seconds_start, seconds_end - offset])
            y_points.extend([rescalings[start]['avg_power'], rescalings[start]['avg_power']])

        ax.plot(x_points, y_points, linestyle=':', label=f"Avg rescaling power", color="black", linewidth=2)

    def get_output_dir(self):
        return self._output_dir

    def set_output_dir(self, d):
        if os.path.isdir(d) and os.path.exists(d):
            self._output_dir = d

    def plot_application_metrics(self, experiment_name, containers, metrics, exp_df, exp_times, exp_rescalings, convergence_point):
        plt.figure(figsize=(15, 5))
        labels = {"x": "Time (s)"}

        # If only one resource is plotted (usage metric + limit metric) don't separate axes and set
        # secondary axis as main axis if energy is plotted
        if len(metrics) <= 2:
            og_y_limit, og_y_ticks_freq = self.__config["HARD_Y_LIMIT"], self.__config["Y_TICKS_FREQUENCY"]
            if "structure.energy.usage" in metrics:
                labels["y1"] = "Power (W)"
                if self.__config["SEPARATE_AXES"]:
                    self.__config["HARD_Y_LIMIT"] = self.__config["HARD_Y_LIMIT_2"]
                    self.__config["Y_TICKS_FREQUENCY"] = self.__config["Y_TICKS_FREQUENCY_2"]
            else:
                labels["y1"] = "CPU (shares)"
            og_separate_axes_value = self.__config.get("SEPARATE_AXES", False)
            self.__config["SEPARATE_AXES"] = False
        else:
            labels["y1"] = "Power (W)"
            labels["y2"] = "CPU (shares)"

        ax1 = plt.gca()
        ax2 = ax1.twinx() if self.__config.get("SEPARATE_AXES", False) else None
        axes = (ax1, ax2)

        max_values = {"all": 0}
        for metric in metrics:
            filtered_df = exp_df.loc[exp_df['metric'] == metric]
            resource = self.__get_resource_from_metric(metric)
            if resource not in max_values:
                max_values[resource] = 0
            for container in containers:
                cont_df = filtered_df.loc[filtered_df['container'] == container]
                max_values[resource] = max(max_values[resource], self.__get_max_value(cont_df, metric))
                max_values["all"] = max(max_values["all"], self.__get_max_value(cont_df, metric))
                self.__plot_metric(axes, cont_df, metric)

        # Add vertical lines when app starts and finishes
        self.__set_vline_plot(axes[0], exp_times["start_app_s"], "Start app")
        self.__set_vline_plot(axes[0], exp_times["end_app_s"], "End app")

        # Plot experiment rescalings only when plotting energy for a single container
        if self.__rescalings_can_be_plotted(containers, metrics, exp_rescalings):
            self.plot_experiment_rescalings(axes[0], exp_rescalings)

        # Get y limits based on max y value found in plotted data
        ylims = self.__get_potential_limits(max_values)

        # Plot convergence point
        if self.__config.get("PLOT_CONVERGENCE_POINT", False):
            self.__plot_convergence_point(axes[0], ylims[0], convergence_point, exp_times)

        # Configure and save plot
        self.__configure_plot(axes, exp_times["end_s"], ylims, labels)
        self.__save_plot(self.__generate_plot_name(experiment_name, metrics, containers))

        # Restore original value
        if len(metrics) <= 2:
            self.__config["HARD_Y_LIMIT"] = og_y_limit
            self.__config["Y_TICKS_FREQUENCY"] = og_y_ticks_freq
            self.__config["SEPARATE_AXES"] = og_separate_axes_value

        plt.close()
