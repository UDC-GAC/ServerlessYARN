import json
from copy import deepcopy

# Default values
DEFAULT_CONFIG = {
    "FONTSIZE": 20,
    "SEPARATE_AXES": False,
    "PLOT_LEGEND": False,
    "PLOT_APP_LABELS": False,
    "PLOT_CONVERGENCE_POINT": False,
}

# Map names to custom axis functions
AXIS_FUNCTION_MAP = {
    "sqrt": (lambda x: x**0.5, lambda x: x**2),
    "square": (lambda x: x**2, lambda x: x**0.5)
}


class PlotConfigLoader:
    def __init__(self, config_source):
        if isinstance(config_source, str):
            if config_source.strip():
                with open(config_source.strip(), 'r') as f:
                    self._loaded_config = json.load(f)
            else:
                self._loaded_config = {}
        elif isinstance(config_source, dict):
            self._loaded_config = config_source
        else:
            raise TypeError("Configuration source must be a path to a JSON file or a dictionary")

    def load(self):
        # Load default values
        config = deepcopy(DEFAULT_CONFIG)

        # Overwrite default values with loaded config
        config.update(self._loaded_config)

        # Get pair of axis functions from the specified name
        if "CUSTOM_X_AXIS_FUNCTION" in config:
            config["CUSTOM_X_AXIS_FUNCTION"] = AXIS_FUNCTION_MAP.get(config["CUSTOM_X_AXIS_FUNCTION"], None)

        # TODO: Check retrieved configuration is valid
        # if config.get("SEPARATE_AXES", False) and "HARD_ENERGY_LIMIT" not in config:
        #     raise ValueError(f"Invalid configuration. If axes are separated a hard energy limit must be defined")

        return config

