from copy import deepcopy

DEFAULT_METRICS_CONFIG = {
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
        "label": "CPU usage (shares)",
        "linestyle": "-",
        "marker": "o",
        "limit": 6400
    },
    "structure.cpu.current": {
        "axis": 0,
        "color": "#a300dc",
        "label": "CPU allocation (shares)",
        "linestyle": "-",
        "marker": "x",
        "limit": 6400
    }
}

DEFAULT_VALUE = {
    "color": "#000000",
    "label": "",
    "linestyle": "-",
    "marker": "",
    "limit": 0
}


class MetricConfigProvider:

    def __init__(self, metrics_config=None):
        self.__metrics_config = deepcopy(DEFAULT_METRICS_CONFIG) if not metrics_config else deepcopy(metrics_config)

    def get(self, metric):
        return self.__metrics_config.get(metric, deepcopy(DEFAULT_VALUE))
