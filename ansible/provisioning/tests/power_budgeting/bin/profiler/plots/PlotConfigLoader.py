from copy import deepcopy

PLOT_PARAMETERS = {
    "default": {
        "FONTSIZE": 20,
        "SEPARATE_AXES": False,
        "PLOT_LEGEND": False,
        "PLOT_APP_LABELS": False,
        "PLOT_CONVERGENCE_POINT": False,
        "X_TICKS_FREQUENCY": 250,
        "CPU_TICKS_FREQUENCY": 20
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
            "HARD_CPU_LIMIT": 110
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
            "HARD_CPU_LIMIT": 110
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
            "HARD_CPU_LIMIT": 110
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
            "HARD_CPU_LIMIT": 110
        }
    },
    "npb_1cont_32threads": {
        "no-capping": {
            "FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": False,
            "X_TICKS_FREQUENCY": 100,
            "CPU_TICKS_FREQUENCY": 500,
            "ENERGY_TICKS_FREQUENCY": 20,
            "MARKER_FREQUENCY": 4,
            "HARD_X_LIMIT": 750,
            "HARD_CPU_LIMIT": 3300,
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
            "HARD_CPU_LIMIT": 3300,
            "HARD_ENERGY_LIMIT": 220
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
            "HARD_CPU_LIMIT": 3300,
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
            "HARD_X_LIMIT": 500,
            "HARD_CPU_LIMIT": 3300,
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
            "HARD_CPU_LIMIT": 3300,
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
