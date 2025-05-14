import os
import numpy as np
import matplotlib.pyplot as plt

import utils.utils as utils
from plots.PlotUtils import PlotUtils
from plots.PlotStyler import PlotStyler
from plots.MetricConfigProvider import MetricConfigProvider
from plots.PlotConfigLoader import PlotConfigLoader

CONTAINER_METRICS = ["proc.cpu.user", "structure.energy.usage"]
APPLICATION_METRICS = ["structure.cpu.current", "structure.energy.max"]


class ExperimentsPlotter:

    def __init__(self, app_name, experiments_group, output_dir=None,
                 config_loader=PlotConfigLoader(), metric_config_provider=MetricConfigProvider()):
        self._output_dir = output_dir
        self._app_name = app_name
        self._experiments_group = experiments_group
        self.__config = config_loader.load_config(app_name, experiments_group)
        self._styler = PlotStyler(self.__config)
        self._metric_config_provider = metric_config_provider

    @staticmethod
    def __scalings_can_be_plotted(containers, resources, exp_rescalings):
        return len(containers) == 1 and len(resources) == 1 and resources[0] == "energy" and exp_rescalings

    @staticmethod
    def __set_potential_limits(resource_config, max_values):
        if "cpu" in resource_config and "cpu" in max_values:
            resource_config["cpu"]["limit"] = PlotUtils.get_nearest_limit(max_values.get("cpu", None))

        if "energy" in resource_config and "energy" in max_values:
            resource_config["energy"]["limit"] = PlotUtils.get_nearest_limit(max_values.get("energy", None))

        return resource_config

    @staticmethod
    def __get_main_resource(resource_config):
        # CPU will always be plotted on the main axis (left axis)
        if "cpu" in resource_config:
            return "cpu"
        # If energy is plotted while CPU is not, energy will be plotted on the main axis
        if "energy" in resource_config:
            return "energy"
        raise ValueError("Neither CPU nor energy exist in resources configuration")

    def __get_max_value(self, df, metric):
        max_y = None
        # First we try to get max y value from data
        try:
            max_y = df['value'].max()
        except Exception as e:
            print(f"An error has occured trying to get max y value from data: {str(e)}.")

        # If no data or bad data is provided we get the maximum default value for this metric
        if not max_y or np.isnan(max_y) or np.isinf(max_y):
            max_y = self._metric_config_provider.get(metric).get("limit", 0)

        return max_y

    def __plot_convergence_point(self, main_axis, main_resource, main_resource_ylim, convergence_point, times):
        # Get the y limit of the figure (higher y tick of the main resource)
        fig_ylim = PlotUtils.generate_ticks(
            self.__config.get(f"HARD_{main_resource.upper()}_LIMIT", main_resource_ylim),
            self.__config.get(f"{main_resource.upper()}_TICKS_FREQUENCY", 20))[-1]

        if convergence_point:
            # If convergence time is negative (method converge before starting) the rectangle is drawn from Start App
            cap_convergence_time = max(convergence_point["time"], times["start_app_s"])

            # Draw a rectangle with red pattern (before convergence)
            main_axis.add_patch(PlotUtils.create_rectangle(
                (times["start_app_s"], 0), cap_convergence_time - times["start_app_s"], fig_ylim, "red", "x"))

            # Plot vertical line at the convergence point
            PlotUtils.plot_vertical_line(main_axis, cap_convergence_time)

            # Draw a rectangle with green pattern (after convergence)
            main_axis.add_patch(PlotUtils.create_rectangle(
                (cap_convergence_time, 0), times["end_app_s"] - cap_convergence_time, fig_ylim, "green", "o"))
        else:
            # Draw a rectangle with red pattern
            main_axis.add_patch(PlotUtils.create_rectangle(
                (times["start_app_s"], 0), times["end_app_s"] - times["start_app_s"], fig_ylim, "red", "x"))

    def __plot_app_lines(self, main_axis, start_app, end_app):
        if self.__config.get("PLOT_APP_LABELS", None):
            PlotUtils.plot_vertical_line(main_axis, start_app, "Start app", self.__config.get("FONTSIZE", 20))
            PlotUtils.plot_vertical_line(main_axis, end_app, "End app", self.__config.get("FONTSIZE", 20))
        else:
            PlotUtils.plot_vertical_line(main_axis, start_app)
            PlotUtils.plot_vertical_line(main_axis, end_app)

    def __plot_metric(self, df, metric, resource_config, container=None):
        metric_config = self._metric_config_provider.get(metric)
        label = f"{metric_config['label']} - {container}" if container else metric_config['label']

        # If there are various containers assign different colors to each one
        color = PlotUtils.custom_color_by_container(metric_config['color'], container)

        # Plot line
        PlotUtils.plot_line(resource_config["ax"], df["elapsed_seconds"], df["value"], label, color,
                            metric_config['linestyle'], metric_config['marker'], self.__config.get("MARKER_FREQUENCY", None))

    def __get_resource_config(self, metrics):
        # If only one resource is plotted (usage metric + limit metric) don't separate axes and set
        # secondary axis as main axis if energy is plotted
        resource_config = {}
        resource_label = {"cpu": "CPU (shares)", "energy": "Power (W)"}
        for metric in metrics:
            resource = utils.get_resource_from_metric(metric)
            if resource not in resource_config:
                resource_config[resource] = {"label": resource_label[resource], "metrics": list()}
            resource_config[resource]["metrics"].append(metric)

        main_axis = None
        if "cpu" in resource_config:
            resource_config["cpu"]["ax"] = main_axis = plt.gca()

        if "energy" in resource_config:
            if main_axis:
                # If CPU is included create a secondary axis for energy just when axes have to be separated
                resource_config["energy"]["ax"] = main_axis.twinx() if self.__config.get("SEPARATE_AXES", False) else main_axis
            else:
                # If not CPU is included, create an axis for energy
                resource_config["energy"]["ax"] = plt.gca()

        return resource_config

    def get_output_dir(self):
        return self._output_dir

    def set_output_dir(self, d):
        if os.path.isdir(d) and os.path.exists(d):
            self._output_dir = d

    def plot_application_metrics(self, experiment_name, containers, metrics, exp_df, exp_times, scalings, convergence_point):
        plt.figure(figsize=(15, 5))

        # Get labels and axes for each resource based on configuration and plotted metrics
        resource_config = self.__get_resource_config(metrics)
        # Get the main resource (commonly CPU, unless only energy is plotted)
        main_resource = self.__get_main_resource(resource_config)
        # Get axis of the main resource
        main_axis = resource_config[main_resource]["ax"]
        # Get end of the plot as potential x limit
        xlim = exp_times["end_s"]

        # Plot all metrics and save its max values
        max_values = {}
        for resource in resource_config:
            for metric in resource_config[resource]["metrics"]:
                filtered_df = exp_df.loc[exp_df['metric'] == metric]
                if resource not in max_values:
                    max_values[resource] = 0
                for container in containers:
                    cont_df = filtered_df.loc[filtered_df['container'] == container]
                    max_values[resource] = max(max_values[resource], self.__get_max_value(cont_df, metric))
                    self.__plot_metric(cont_df, metric, resource_config[resource])

        # Set the max value of each plotted resource as potential y limit
        resource_config = self.__set_potential_limits(resource_config, max_values)

        # Add vertical lines when app starts and finishes
        self.__plot_app_lines(main_axis, exp_times["start_app_s"], exp_times["end_app_s"])

        # Plot experiment scalings only when plotting energy for a single container
        if self.__scalings_can_be_plotted(containers, list(resource_config.keys()), scalings):
            PlotUtils.plot_power_between_periods(main_axis, scalings)

        # Plot convergence point
        if self.__config.get("PLOT_CONVERGENCE_POINT", False):
            self.__plot_convergence_point(main_axis, main_resource, resource_config[main_resource]["limit"],
                                          convergence_point, exp_times)

        # Configure plot style and save plot
        self._styler.apply_all(resource_config, main_resource, xlim)
        PlotUtils.save_plot(self._output_dir, experiment_name, list(resource_config.keys()), containers)

        plt.close()
