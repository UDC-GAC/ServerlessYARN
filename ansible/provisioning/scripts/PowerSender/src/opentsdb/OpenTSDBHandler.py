import requests
import json

DEFAULT_HEADERS = {'Content-Type': 'application/json'}


class OpenTSDBHandler:

    def __init__(self, opentsdb_ip, opentsdb_port):
        self.opentsdb_url = "http://{0}:{1}/api/put".format(opentsdb_ip, opentsdb_port)
        self.session = requests.Session()
        self.headers = DEFAULT_HEADERS

    def close_connection(self):
        self.session.close()

    def send_data(self, data):
        try:
            # Send data to OpenTSDB
            r = self.session.post(self.opentsdb_url, data=json.dumps(data), headers=self.headers)
            if r.status_code != 204:
                r.raise_for_status()
        except Exception as e:
            raise Exception(f"Error sending data to OpenTSDB: {e}") from e
