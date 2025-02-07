import os
import hashlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

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

    def __set_plot_labels(self, axes, xlabel, ylabel1, ylabel2):
        fontsize = self.__config.get("DEFAULT_FONTSIZE", 20)
        if self.__config.get("SEPARATE_AXES", False):
            axes[0].set_xlabel(xlabel, fontsize=fontsize)
            axes[0].set_ylabel(ylabel1, fontsize=fontsize)
            axes[1].set_ylabel(ylabel2, fontsize=fontsize)
        else:
            axes[0].set_xlabel(xlabel, fontsize=fontsize)
            axes[0].set_ylabel(f"{ylabel1} / {ylabel2}", fontsize=fontsize)

    def __set_plot_limits(self, axes, xlim, ylims):
        if self.__config.get("SEPARATE_AXES", False):
            axes[0].set_xlim(0, self.__config.get("HARD_X_LIMIT", xlim))
            axes[0].set_ylim(0, self.__config.get("HARD_Y_LIMIT", ylims[0]))
            axes[1].set_ylim(0, self.__config.get("SECONDARY_HARD_Y_LIMIT", ylims[1]))
        else:
            axes[0].set_xlim(0, self.__config.get("HARD_X_LIMIT", xlim))
            axes[0].set_ylim(0, self.__config.get("HARD_Y_LIMIT", ylims[0]))

    def __generate_ticks(self, limit):
        return np.linspace(0, limit, self.__config.get("NUM_TICKS", 8))

    def __set_plot_yticks(self, axes, ylims):
        if self.__config.get("SEPARATE_AXES", False):
            axes[0].set_yticks(self.__generate_ticks(self.__config.get("HARD_Y_LIMIT", ylims[0])))
            axes[1].set_yticks(self.__generate_ticks(self.__config.get("SECONDARY_HARD_Y_LIMIT", ylims[1])))
        else:
            axes[0].set_yticks(self.__generate_ticks(self.__config.get("HARD_Y_LIMIT", ylims[0])))

    def __set_legend(self, ax):
        ax.legend(loc='upper center',
                  bbox_to_anchor=(0.66, 0.60),
                  ncol=2,
                  fontsize=self.__config.get("DEFAULT_FONTSIZE", 20) + 2,
                  markerscale=2,
                  facecolor="lightblue",
                  framealpha=0.75)

    def __configure_plot(self, axes, xlim, ylims):
        self.__set_plot_basic_config(axes)
        self.__set_plot_limits(axes, xlim, ylims)
        self.__set_plot_yticks(axes, ylims)
        self.__set_plot_labels(axes, "Time (s)", "CPU (shares)", "Power (W)")
        if self.__config.get("PLOT_LEGEND", False):
            self.__set_legend(axes[0])

    def __annotate_point(self, ax, x, y):
        ax.annotate(f"({x}s, {y:.2f}W)",
                    arrowprops=dict(facecolor='black', arrowstyle="->"),
                    xy=(x + self.__config.get("CONVERGENCE_POINT_OFFSET", (0, 0))[0],
                        y + self.__config.get("CONVERGENCE_POINT_OFFSET", (0, 0))[1]),
                    xytext=(x + self.__config.get("CONVERGENCE_TEXT_OFFSET", (0, 0))[0],
                            y + self.__config.get("CONVERGENCE_TEXT_OFFSET", (0, 0))[1]),  # x+5, y | x+20, y+10
                    fontsize=self.__config["DEFAULT_FONTSIZE"])

    def __set_vline_plot(self, ax, point, label):
        ax.axvline(x=point, color='black', linestyle='--', linewidth=1.25, zorder=-2)
        # Add text on the X axis if provided
        if self.__config["PLOT_APP_LABELS"]:
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
    def plot_experiment_rescalings(rescalings):
        timestamps = sorted(rescalings.keys())
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

    def set_output_dir(self, d):
        if os.path.isdir(d) and os.path.exists(d):
            self._output_dir = d

    def plot_application_metrics(self, experiment_name, containers, metrics, exp_df, exp_times, exp_rescalings, convergence_point):
        plt.figure(figsize=(15, 5))
        ax1 = plt.gca()
        ax2 = ax1.twinx() if self.__config.get("SEPARATE_AXES", False) else None
        axes = (ax1, ax2)

        # If only one resource is plotted (usage metric + limit metric) don't separate axes
        if len(metrics) <= 2:
            og_separate_axes_value = self.__config.get("SEPARATE_AXES", False)
            self.__config["SEPARATE_AXES"] = False

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

        # Plot convergence point
        if self.__config.get("PLOT_CONVERGENCE_POINT", False) and convergence_point:
            self.__annotate_point(axes[0], convergence_point["time"], convergence_point["value"])

        # Plot experiment rescalings only when plotting energy for a single container
        if self.__rescalings_can_be_plotted(containers, metrics, exp_rescalings):
            self.plot_experiment_rescalings(exp_rescalings)

        # Get y limits based on max y value found in plotted data
        ylims = self.__get_potential_limits(max_values)

        # Configure and save plot
        self.__configure_plot(axes, exp_times["end_s"], ylims)
        self.__save_plot(self.__generate_plot_name(experiment_name, metrics, containers))

        # Restore original value
        if len(metrics) <= 2:
            self.__config["SEPARATE_AXES"] = og_separate_axes_value

        plt.close()
