import requests
import json
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

# Dates management
start_dt = datetime(2024, 7, 28, 11, 30, 0)  # Change this dates
end_dt = datetime(2024, 7, 28, 11, 50, 0)
start_str = start_dt.strftime("%Y-%m-%d_%H-%M-%S")
end_str = end_dt.strftime("%Y-%m-%d_%H-%M-%S")
start_time = int(start_dt.timestamp())
end_time = int(end_dt.timestamp())

# OpenTSDB management
opentsdb_url = "http://127.0.0.1:4242/api/query"
metrics = ["proc.cpu.user", "structure.energy.usage"]
hosts = ["compute-2-5-cont1", "compute-2-5-cont0", "compute-2-4-cont1", "compute-2-4-cont0",
         "compute-2-3-cont1", "compute-2-3-cont0", "compute-2-2-cont1", "compute-2-2-cont0"]
tags = {"host": "|".join(hosts)}


def get_opentsdb_data(metric, tags, start, end, aggregator="sum", downsample="5s-avg"):
    query = {
        "start": start,
        "end": end,
        "queries": [
            {
                "metric": metric,
                "aggregator": aggregator,
                "downsample": downsample,
                "tags": tags
            }
        ]
    }
    print(query)
    response = requests.post(opentsdb_url, data=json.dumps(query))
    data = response.json()
    return data


def plot_data(data, metric_name, start, end):
    plt.figure(figsize=(10, 5))
    for ts in data:
        dps = ts['dps']
        df = pd.DataFrame(list(dps.items()), columns=['timestamp', 'value'])
        df['timestamp'] = pd.to_numeric(df['timestamp'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        plt.plot(df['timestamp'], df['value'], label=ts['tags']['host'])

    plt.title(metric_name)
    plt.xlabel('Time')
    plt.ylabel(metric_name)
    plt.legend()
    plt.grid(True)
    plt.savefig(f"{metric_name}_{start}_{end}.png")
    plt.show()


for metric in metrics:
    data = get_opentsdb_data(metric, tags, start_time, end_time)
    plot_data(data, metric, start_str, end_str)

