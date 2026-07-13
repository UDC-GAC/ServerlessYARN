import requests
import json
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {'Content-Type': 'application/json'}

def web_request(url, operation, error_message, data=None, headers=DEFAULT_HEADERS, session=None):

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