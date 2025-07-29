import matplotlib.pyplot as plt
from plots.PlotUtils import PlotUtils


class PlotStyler:

    def __init__(self, config):
        self.__config = config

    def set_grid_and_fontsize(self, resource_config):
        plt.grid(True)  # Grid is always added
        fontsize = self.__config.get("FONTSIZE", 20)
        # Set axis for each plotted resource
        for res in resource_config:
            resource_config[res]["ax"].tick_params(axis='both', labelsize=fontsize)

    def __set_ax_ticks(self, ax, ax_name, default_limit):
        limit = self.__config.get(f"HARD_{ax_name}_LIMIT", default_limit)
        ticks_frequency = self.__config.get(f"{ax_name}_TICKS_FREQUENCY", round(limit / 10))
        if ax_name == "X":
            ax.set_xticks(PlotUtils.generate_ticks(limit, ticks_frequency))
        else:
            ax.set_yticks(PlotUtils.generate_ticks(limit, ticks_frequency))

    def set_ticks(self, resource_config, main_resource, xlim):
        # If configured set a custom X-axis scale defined by a tuple of functions (forward, inverse)
        # e.g., (lambda x: x**(1/2), lambda x: x**2)
        if self.__config.get("CUSTOM_X_AXIS_FUNCTION", None):
            resource_config[main_resource]["ax"].set_xscale('function', functions=self.__config.get("CUSTOM_X_AXIS_FUNCTION", None))
        # If configured set a list of custom X ticks
        # e.g., [0, 50, 125, 250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250]
        if self.__config.get("CUSTOM_X_AXIS_VALUES", None):
            resource_config[main_resource]["ax"].set_xticks(self.__config.get("CUSTOM_X_AXIS_VALUES", None))
        else:
            # Generate X ticks based on X limit and X ticks frequency
            self.__set_ax_ticks(resource_config[main_resource]["ax"], "X", xlim)

        # Set main resource y ticks
        self.__set_ax_ticks(resource_config[main_resource]["ax"], main_resource.upper(), resource_config[main_resource]["limit"])

        # If main resource is CPU and energy is included while axes have to be separated, set xticks for energy axis
        if main_resource == "cpu" and "energy" in resource_config and self.__config.get("SEPARATE_AXES", False):
            self.__set_ax_ticks(resource_config["energy"]["ax"], "ENERGY", resource_config["energy"]["limit"])

    def set_limits(self, resource_config, main_resource, xlim):
        # Set main resource limits
        resource_config[main_resource]["ax"].set_xlim(0, self.__config.get("HARD_X_LIMIT", xlim))
        resource_config[main_resource]["ax"].set_ylim(0, self.__config.get(f"HARD_{main_resource.upper()}_LIMIT",
                                                                           resource_config[main_resource]["limit"]))

        # If main resource is CPU and energy is included while axes have to be separated, set limit for energy axis
        if main_resource == "cpu" and "energy" in resource_config and self.__config.get("SEPARATE_AXES", False):
            resource_config["energy"]["ax"].set_ylim(0, self.__config.get("HARD_ENERGY_LIMIT",
                                                                          resource_config["energy"]["limit"]))

    def set_labels(self, resource_config, main_resource):
        fontsize = self.__config.get("FONTSIZE", 20)

        # Set X-axis label
        resource_config[main_resource]["ax"].set_xlabel("Time (s)", fontsize=fontsize)

        if "cpu" in resource_config and "energy" in resource_config:
            if self.__config.get("SEPARATE_AXES", False):
                # If both resources are plotted and axes are separated set different labels for each y-axis
                resource_config["cpu"]["ax"].set_ylabel(resource_config["cpu"]["label"], fontsize=fontsize)
                resource_config["energy"]["ax"].set_ylabel(resource_config["energy"]["label"], fontsize=fontsize)
            else:
                # If both resources share axis set a label combining their names
                combined_label = f"{resource_config['cpu']['label']} / {resource_config['energy']['label']}"
                resource_config["cpu"]["ax"].set_ylabel(combined_label, fontsize=fontsize)
        else:
            resource_config[main_resource]["ax"].set_ylabel(resource_config[main_resource]["label"], fontsize=fontsize)

    def set_legend(self, resource_config, main_resource):
        all_handles = []
        all_labels = []
        seen_axes = set()

        for resource in resource_config.values():
            ax = resource["ax"]
            if ax not in seen_axes:
                handles, labels = ax.get_legend_handles_labels()
                all_handles.extend(handles)
                all_labels.extend(labels)
                seen_axes.add(ax)

        resource_config[main_resource]["ax"].legend(
            all_handles,
            all_labels,
            loc='upper left',
            bbox_to_anchor=(0.66, 0.6),
            ncol=1,
            fontsize=self.__config.get("FONTSIZE", 20) + 2,
            markerscale=2,
            facecolor="lightblue",
            framealpha=0.75)

    def apply_all(self, resource_config, main_resource, xlim):
        self.set_grid_and_fontsize(resource_config)
        self.set_ticks(resource_config, main_resource, xlim)
        self.set_limits(resource_config, main_resource, xlim)
        self.set_labels(resource_config, main_resource)
        if self.__config.get("PLOT_LEGEND", False):
            self.set_legend(resource_config, main_resource)
