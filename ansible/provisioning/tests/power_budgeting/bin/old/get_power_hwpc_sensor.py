import requests
import json
from datetime import datetime, timedelta

OPENTSDB_URL = "http://127.0.0.1:4242/api/query"
METRICS = ["proc.cpu.user", "structure.energy.usage", "structure.cpu.current", "structure.energy.max"]
#METRICS = ["structure.energy.usage", "structure.energy.max"]
HOSTS = ["hwpc-sensor"]
Y_MAX = 250
TAGS = {
    "structure.energy.usage": {"host": "|".join(HOSTS)},
    "structure.energy.max": {"structure": "|".join(HOSTS)},
    "proc.cpu.user": {"host": "|".join(HOSTS)},
    "structure.cpu.current": {"structure": "|".join(HOSTS)}
}
COLORS = {
    "structure.energy.usage": "#ffc500",
    "structure.energy.max": "#dc0000",
    "proc.cpu.user": "#1f77b4",
    "structure.cpu.current": "#a300dc"
}
VALUES_TO_FIND_EXP = {
    "serverless_fixed_value": 70,
    "serverless_dynamic_value": 1593,
    "serverless_static_model": 1701,
    "serverless_dynamic_model": 60
}

def get_opentsdb_data(metric, start, end, aggregator="sum", downsample="1s-avg"):
    query = {
        "start": start,
        "end": end,
        "queries": [
            {
                "metric": metric,
                "aggregator": aggregator,
                "downsample": downsample,
                "tags": TAGS[metric]
            }
        ]
    }
    response = requests.post(OPENTSDB_URL, data=json.dumps(query))

    return response.json()


def get_average_power(data):
    total_power = 0
    num_samples = 0
    for values in data:
        dps = values['dps']
        for ts in dps:
            print(dps[ts])
            total_power += dps[ts]
            num_samples += 1

    average_power = total_power / num_samples

    print(f"Average power consumption for HWPC-Sensor is {average_power}")


if __name__ == "__main__":

    # Gather data for these dates
    start_dt = datetime(2024, 9, 18, 12, 55, 0)
    end_dt = datetime.now()
    start_time = int(start_dt.timestamp())
    end_time = int(end_dt.timestamp())
    data = get_opentsdb_data("structure.energy.usage", start_time, end_time)

    #print(data)

    get_average_power(data)
