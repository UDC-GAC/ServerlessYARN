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

    def set_ticks(self, resource_config, main_resource, xlim):
        # If configured set a custom X-axis scale defined by a tuple of functions (forward, inverse)
        # e.g., (lambda x: x**(1/2), lambda x: x**2)
        if self.__config.get("CUSTOM_X_AXIS_FUNCTIONS", None):
            resource_config[main_resource]["ax"].set_xscale('function', functions=self.__config.get("CUSTOM_X_AXIS_FUNCTIONS", None))
        # If configured set a list of custom X ticks
        # e.g., [0, 50, 125, 250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250]
        if self.__config.get("CUSTOM_X_AXIS_VALUES", None):
            resource_config[main_resource]["ax"].set_xticks(self.__config.get("CUSTOM_X_AXIS_VALUES", None))
        else:
            # Generate X ticks based on X limit and X ticks frequency
            resource_config[main_resource]["ax"].set_xticks(PlotUtils.generate_ticks(
                self.__config.get("HARD_X_LIMIT", xlim), self.__config.get("X_TICKS_FREQUENCY", 20)))

        # Set main resource y ticks
        resource_config[main_resource]["ax"].set_yticks(PlotUtils.generate_ticks(
            self.__config.get(f"HARD_{main_resource.upper()}_LIMIT", resource_config[main_resource]["limit"]),
            self.__config.get(f"{main_resource.upper()}_TICKS_FREQUENCY", 20)))

        # If main resource is CPU and energy is included while axes have to be separated, set xticks for energy axis
        if main_resource == "cpu" and "energy" in resource_config and self.__config.get("SEPARATE_AXES", False):
            resource_config["energy"]["ax"].set_yticks(
                PlotUtils.generate_ticks(self.__config.get("HARD_ENERGY_LIMIT", resource_config["energy"]["limit"]),
                                         self.__config.get("ENERGY_TICKS_FREQUENCY", 20)))

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
        resource_config[main_resource]["ax"].legend(loc='upper center',
                                                    bbox_to_anchor=(0.66, 0.60),
                                                    ncol=2,
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
