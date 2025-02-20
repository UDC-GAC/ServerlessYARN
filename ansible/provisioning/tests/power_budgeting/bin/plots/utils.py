import os
import json
import requests
import pandas as pd


def create_dir(d):
    os.makedirs(d, exist_ok=True)


def remove_file(f):
    if os.path.exists(f):
        os.remove(f)


def file_exists(f):
    return os.path.exists(f) and os.path.isfile(f)


def print_dict(d):
    for key, value in d.items():
        print(f"{key}: {value}")


def value_is_near_limit(value, limit, offset):
    return limit * (1 - offset) < value < limit * (1 + offset)


def get_df_col_avg(df, col):
    return df[col].mean()


def filter_df_by_metric(df, metric, metric_col='metric'):
    return df.loc[df[metric_col] == metric]


def filter_df_by_period(df, start=None, end=None, time_col='elapsed_seconds'):
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df[time_col] >= start
    if end is not None:
        mask &= df[time_col] <= end
    return df.loc[mask]


def get_tags(metric, containers):
    if metric in ["structure.energy.usage", "proc.cpu.user"]:
        field_name = "host"
    elif metric in ["structure.energy.max", "structure.cpu.current"]:
        field_name = "structure"
    else:
        raise Exception(f"Metric {metric} is not supported. Failed while fetching a tag for this metric")

    return {field_name: "|".join(containers)}


def get_opentsdb_data(url, metric, containers, start, end, aggregator="zimsum", downsample="5s-avg"):
    query = {
        "start": start,
        "end": end,
        "queries": [
            {
                "metric": metric,
                "aggregator": aggregator,
                "downsample": downsample,
                "tags": get_tags(metric, containers)
            }
        ]
    }
    response = requests.post(url, data=json.dumps(query))

    return response.json()


def compute_avg_per_interval(intervals, df, metric):
    timestamps = sorted(intervals.keys())
    power_df = df.loc[df['metric'] == metric]
    for start, end in zip(timestamps, timestamps[1:]):
        seconds_start = intervals[start]['elapsed_seconds']
        seconds_end = intervals[end]['elapsed_seconds']
        filtered_df = filter_df_by_period(power_df, start=seconds_start, end=seconds_end)
        intervals[start]['avg_power'] = filtered_df['value'].mean()

    return intervals
