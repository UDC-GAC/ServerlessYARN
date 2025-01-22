import os
import json
import requests


def create_dir(d):
    os.makedirs(d, exist_ok=True)


def remove_file(f):
    if os.path.exists(f):
        os.remove(f)


def file_exists(f):
    return os.path.exists(f) and os.path.isfile(f)


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
