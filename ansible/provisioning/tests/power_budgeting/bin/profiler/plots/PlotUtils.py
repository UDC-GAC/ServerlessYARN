import hashlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as patches


class PlotUtils:

    @staticmethod
    def get_nearest_limit(n):
        # Check n has a valid value
        if not n:
            return None
        # Returns the nearest limit from a list of predefined limits
        for lim in [100, 200, 400, 800, 1600]:
            if n <= lim:
                return lim
        return 3200

    @staticmethod
    def generate_ticks(limit, ticks_frequency):
        # It adds an offset if limit is between one tick and the next
        # Example: limit=107, ticks_frequency=20 -> 107 + (20 - (107 % 20)) % 20 = 107 + 13 % 20 = 120
        #          limit=100, ticks_frequency=20 -> 100 + (20 - (100 % 20)) % 20 = 107 + 20 % 20 = 100
        return np.arange(0, limit + (ticks_frequency - (limit % ticks_frequency)) % ticks_frequency + 1, ticks_frequency)

    @staticmethod
    def generate_plot_name(experiment_name, resources, containers):
        resource = None
        container = None
        if len(resources) == 1:
            resource = resources[0]
        if len(containers) == 1:
            container = containers[0]
        # ATM: Containers are ignored as this is only used for single-container applications
        return experiment_name + (f"_{resource}" if resource else "")  # + (f"_{container}" if container else "")

    @staticmethod
    def create_rectangle(left_corner, width, height, color, pattern):
        return patches.Rectangle(left_corner, width, height, color=color, alpha=0.2, hatch=pattern, linewidth=0, edgecolor=None)

    @staticmethod
    def custom_color_by_container(color, container=None):
        if not container:
            return color

        # Generate a consistent color variation for the container
        hash_value = int(hashlib.md5(container.encode()).hexdigest(), 16)  # Hash container name
        base_rgb = mcolors.to_rgb(color)  # Convert hex to RGB
        variation = (hash_value % 256) / 256  # Generate a variation factor between 0 and 1

        # Adjust the brightness of the metric color based on the variation factor
        adjusted_rgb = tuple(min(1, max(0, c + variation * 0.5 - 0.25)) for c in base_rgb)

        return mcolors.to_hex(adjusted_rgb)  # Convert RGB back to hex

    @staticmethod
    def save_plot(out_dir, experiment_name, resources, containers, format='png'):
        filename = PlotUtils.generate_plot_name(experiment_name, resources, containers)
        plt.tight_layout()
        plt.savefig(f'{out_dir}/{filename}.{format}', bbox_inches='tight')

    @staticmethod
    def plot_line(ax, x, y, label, color, linestyle, marker, marker_frequency=None):
        ax.plot(x, y,
                label=label,
                color=color,
                linestyle=linestyle,
                marker=marker,
                markersize=12,
                markevery=marker_frequency)

    @staticmethod
    def plot_vertical_line(ax, point, label=None, fontsize=None):
        ax.axvline(x=point, color='black', linestyle='--', linewidth=4, zorder=-2)
        # Add text on the X axis if provided
        if label:
            ylim = ax.get_ylim()[1]
            ax.annotate(label, xy=(point+5, ylim - 10), xytext=(point+5, ylim - 10), fontsize=fontsize)

    @staticmethod
    def plot_power_between_periods(ax, periods, label=None):
        # Periods must have the form:
        # {
        #   <datetime>: {
        #       "elapsed_seconds": <int>,
        #       "avg_power": <float>
        #       }
        # }
        timestamps = sorted(periods.keys())
        offset = 0.00001

        x_points = []
        y_points = []
        for start, end in zip(timestamps, timestamps[1:]):
            seconds_start = periods[start]['elapsed_seconds']
            seconds_end = periods[end]['elapsed_seconds']
            x_points.extend([seconds_start, seconds_end - offset])
            y_points.extend([periods[start]['avg_power'], periods[start]['avg_power']])

        ax.plot(x_points, y_points, linestyle=':', label=label, color="#50C878", linewidth=6)
