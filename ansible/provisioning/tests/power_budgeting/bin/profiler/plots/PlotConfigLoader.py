from copy import deepcopy

PLOT_PARAMETERS = {
    "default": {
        "FONTSIZE": 20,
        "SEPARATE_AXES": False,
        "PLOT_LEGEND": False,
        "PLOT_APP_LABELS": False,
        "PLOT_CONVERGENCE_POINT": False,
    },
    "npb_1cont_1thread": {
        "no-capping": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": True,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": False,
            "X_TICKS_FREQUENCY": 250,
            "CPU_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 2250,
            "HARD_CPU_LIMIT": 120
        },
        "min": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "X_TICKS_FREQUENCY": 250,
            "CPU_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 2250,
            "HARD_CPU_LIMIT": 120,
            #"CUSTOM_X_AXIS_VALUES": [0, 50, 125, 250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250],
            #"CUSTOM_X_AXIS_FUNCTIONS": (lambda x: x**(1/2), lambda x: x**2)
        },
        "medium": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "X_TICKS_FREQUENCY": 250,
            "CPU_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 2000,
            "HARD_CPU_LIMIT": 120
        },
        "max": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "X_TICKS_FREQUENCY": 250,
            "CPU_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 1900,
            "HARD_CPU_LIMIT": 110
        },
        "dynamic_power_budget": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": False,
            "X_TICKS_FREQUENCY": 250,
            "CPU_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 1750,
            "HARD_CPU_LIMIT": 120,
            "HARD_ENERGY_LIMIT": 85
        }
    },
    "npb_1cont_32threads": {
        "no-capping": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": True,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": False,
            "X_TICKS_FREQUENCY": 100,
            "CPU_TICKS_FREQUENCY": 500,
            "ENERGY_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 4,
            "HARD_X_LIMIT": 750,
            "HARD_CPU_LIMIT": 3500,
            "HARD_ENERGY_LIMIT": 220
        },
        "min": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "X_TICKS_FREQUENCY": 100,
            "CPU_TICKS_FREQUENCY": 500,
            "ENERGY_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 4,
            "HARD_X_LIMIT": 750,
            "HARD_CPU_LIMIT": 3500,
            "HARD_ENERGY_LIMIT": 220,
            #"CUSTOM_X_AXIS_VALUES": [0, 25, 50, 100, 150, 200, 300, 400, 500],
            #"CUSTOM_X_AXIS_FUNCTIONS": (lambda x: x**(1/2), lambda x: x**2)
        },
        "medium": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "X_TICKS_FREQUENCY": 100,
            "CPU_TICKS_FREQUENCY": 500,
            "ENERGY_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 4,
            "HARD_X_LIMIT": 600,
            "HARD_CPU_LIMIT": 3500,
            "HARD_ENERGY_LIMIT": 220
        },
        "max": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "X_TICKS_FREQUENCY": 100,
            "CPU_TICKS_FREQUENCY": 500,
            "ENERGY_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 4,
            "HARD_X_LIMIT": 600,
            "HARD_CPU_LIMIT": 3500,
            "HARD_ENERGY_LIMIT": 220
        },
        "dynamic_power_budget": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": False,
            "X_TICKS_FREQUENCY": 100,
            "CPU_TICKS_FREQUENCY": 500,
            "ENERGY_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 4,
            "HARD_X_LIMIT": 800,
            "HARD_CPU_LIMIT": 3500,
            "HARD_ENERGY_LIMIT": 200
        }
    }
}


class PlotConfigLoader:

    @staticmethod
    def load_config(app_name, experiments_group):
        config = deepcopy(PLOT_PARAMETERS.get(app_name, {}).get(experiments_group, PLOT_PARAMETERS.get("default", {})))

        # Check retrieved configuration is valid
        # if config.get("SEPARATE_AXES", False) and "HARD_ENERGY_LIMIT" not in config:
        #     raise ValueError(f"Invalid configuration for app {app_name} in experiments group {experiments_group}"
        #                      f"If axes are separated a hard energy limit must be defined")

        return config
