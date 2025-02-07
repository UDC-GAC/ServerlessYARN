PLOT_PARAMETERS = {
    "default": {
        "DEFAULT_FONTSIZE": 20,
        "SEPARATE_AXES": False,
        "PLOT_LEGEND": False,
        "PLOT_APP_LABELS": False,
        "PLOT_CONVERGENCE_POINT": False,
        "CONVERGENCE_POINT_OFFSET": (0, 0),
        "CONVERGENCE_TEXT_OFFSET": (0, 0),
    },
    "npb_1cont_1thread": {
        "no-capping": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": True,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": False,
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 2100,
            "HARD_Y_LIMIT": 110
        },
        "min": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "CONVERGENCE_POINT_OFFSET": (0, 0),
            "CONVERGENCE_TEXT_OFFSET": (20, 20),
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 2100,
            "HARD_Y_LIMIT": 110
        },
        "medium": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "CONVERGENCE_POINT_OFFSET": (0, 0),
            "CONVERGENCE_TEXT_OFFSET": (0, 0),
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 2100,
            "HARD_Y_LIMIT": 110
        },
        "max": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "CONVERGENCE_POINT_OFFSET": (0, 0),
            "CONVERGENCE_TEXT_OFFSET": (0, 0),
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 2100,
            "HARD_Y_LIMIT": 110
        },
        "dynamic_power_budget": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": False,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "CONVERGENCE_POINT_OFFSET": (0, 0),
            "CONVERGENCE_TEXT_OFFSET": (0, 0),
            "MARKER_FREQUENCY": 10,
            "HARD_X_LIMIT": 2100,
            "HARD_Y_LIMIT": 110
        }
    },
    "npb_1cont_32threads": {
        "no-capping": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "CONVERGENCE_POINT_OFFSET": (0, 0),
            "CONVERGENCE_TEXT_OFFSET": (0, 0),
            "HARD_X_LIMIT": 700
            #"HARD_Y_LIMIT": 3300,
            #"SECONDARY_HARD_Y_LIMIT": 200
        },
        "min": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "CONVERGENCE_POINT_OFFSET": (0, 0),
            "CONVERGENCE_TEXT_OFFSET": (0, 0),
            "HARD_X_LIMIT": 700
            #"HARD_Y_LIMIT": 3300,
            #"SECONDARY_HARD_Y_LIMIT": 200
        },
        "medium": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "CONVERGENCE_POINT_OFFSET": (0, 0),
            "CONVERGENCE_TEXT_OFFSET": (0, 0),
            "HARD_X_LIMIT": 700
            #"HARD_Y_LIMIT": 3300,
            #"SECONDARY_HARD_Y_LIMIT": 200
        },
        "max": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "CONVERGENCE_POINT_OFFSET": (0, 0),
            "CONVERGENCE_TEXT_OFFSET": (0, 0),
            "HARD_X_LIMIT": 500
            #"HARD_Y_LIMIT": 3300,
            #"SECONDARY_HARD_Y_LIMIT": 200
        },
        "dynamic_power_budget": {
            "DEFAULT_FONTSIZE": 20,
            "SEPARATE_AXES": True,
            "PLOT_LEGEND": False,
            "PLOT_APP_LABELS": False,
            "PLOT_CONVERGENCE_POINT": True,
            "CONVERGENCE_POINT_OFFSET": (0, 0),
            "CONVERGENCE_TEXT_OFFSET": (0, 0),
            "HARD_X_LIMIT": 500
            #"HARD_Y_LIMIT": 3300,
            #"SECONDARY_HARD_Y_LIMIT": 200
        }
    }
}
