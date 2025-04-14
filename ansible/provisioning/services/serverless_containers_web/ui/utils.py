import requests
import json
from bs4 import BeautifulSoup

DEFAULT_APP_VALUES = {
    "install_script": "install.sh",
    "start_script": "start.sh",
    "stop_script": "stop.sh",
    "files_dir": "files_dir"
}

DEFAULT_LIMIT_VALUES = {
    "boundary": 10,
    "boundary_type": "percentage_of_max"
}

DEFAULT_RESOURCE_VALUES = {
    "weight": 1
}

DEFAULT_HDFS_VALUES = {
    "local_output": "/user/root",
    "global_output": "/user/root"
}

DEFAULT_HEADERS = {'Content-Type': 'application/json'}

def request_to_state_db(url, operation, error_message, data=None, headers=DEFAULT_HEADERS, session=None):

    if session: request_session = session
    else: request_session = requests

    if operation == "put": http_operation = request_session.put
    elif operation == "post": http_operation = request_session.post
    elif operation == "delete": http_operation = request_session.delete
    else: raise Exception("HTTP operation {0} not supported, use one of {1}".format(operation, ["put", "post", "delete"]))

    if data: response = http_operation(url, data=json.dumps(data), headers=headers)
    else: response = http_operation(url, headers=headers)

    error = ""
    if (response != "" and not response.ok):
        soup = BeautifulSoup(response.text, features="html.parser")
        error = "{0}: {1}".format(error_message, soup.get_text().strip())

    return error, response