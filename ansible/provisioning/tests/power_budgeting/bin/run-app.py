import sys
import time
import redis
import requests
from urllib.parse import urljoin
from datetime import datetime, timezone

WEB_INTERFACE_URL = "http://localhost:9000"
ORCHESTRATOR_URL = "http://localhost:5000"
NUMBER_OF_CONTAINERS = "1"
ASSIGNATION_POLICY = "Best-effort"
BENEVOLENCE = "3"  # 1: "Lax", 2: "Medium", 3: "Strict"
POLLING_FREQUENCY = 5


def get_csrf_token(session):
    # Do some random request to get CSRF token
    response = session.get(urljoin(WEB_INTERFACE_URL, "/ui/apps"))

    if response.status_code != 200:
        raise Exception("Error doing GET request in order to get CSRF token")

    # Extract CSRF token from cookies
    for cookie in session.cookies:
        if cookie.name == 'csrftoken':
            return cookie.value

    raise Exception("CSRF token not found in cookies")


def start_app(session, app_name):

    # Get CSRF token
    csrf_token = get_csrf_token(session)

    # Set headers
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrf_token,
    }

    # Set data
    data = {
        "csrfmiddlewaretoken": csrf_token,
        "operation": "add",
        "structure_type": "containers_to_app",
        "name": app_name,
        "number_of_containers": NUMBER_OF_CONTAINERS,
        "assignation_policy": ASSIGNATION_POLICY,
        "benevolence": BENEVOLENCE,
        "save": "Start App",
    }

    # Start app through web interface
    response = session.post(urljoin(WEB_INTERFACE_URL, "/ui/apps"), headers=headers, data=data)

    if response.status_code != 200:
        raise Exception(f"Failed to start app through web interface: {response}")


def get_app_redis_key(redis_server, app_name):
    for key in redis_server.scan_iter("{0}:*".format("pending_tasks")):
        task_name = redis_server.hget(key, "task_name").decode("utf-8")
        if task_name.startswith(app_name):
            return key
    raise Exception(f"Redis key for app {app_name} not found")


def get_containers_from_app(session, app_name):
    response = session.get(urljoin(ORCHESTRATOR_URL, f"/structure/{app_name}"))
    if 'containers' in response.json():
        return response.json()['containers']
    else:
        raise Exception(f"No containers found for app {0}: {1}".format(app_name, response.json()))


def update_containers_file(file, containers):
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S%z')
    with open(file, 'a') as f:
        for container in containers:
            f.write(f"{current_time} {container}\n")


def wait_for_app_to_finish(session, redis_server, app_name):
    app_running = True
    app_key = get_app_redis_key(redis_server, app_name)
    while app_running:
        # Run a GET request to the web interface to force the update of tasks status in redis
        response = session.get(urljoin(WEB_INTERFACE_URL, "/ui/apps"))
        try:
            task = redis_server.hget(app_key, "task_name")
            if not task:
                app_running = False
        except Exception as e:
            app_running = False
            print(str(e))

        time.sleep(POLLING_FREQUENCY)


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("At least 1 argument is needed")
        print("1 -> app name (e.g., npb_app)")
        print("2 -> containers file (e.g., ./out/containers)")
        sys.exit(0)

    app_name = sys.argv[1]
    containers_file = sys.argv[2]

    web_interface_session = requests.Session()
    orchestrator_session = requests.Session()
    redis_server = redis.StrictRedis()

    start_app(web_interface_session, app_name)
    time.sleep(60)  # Wait some time for the app to be subscribed to SC
    containers = get_containers_from_app(orchestrator_session, app_name)
    update_containers_file(containers_file, containers)

    wait_for_app_to_finish(web_interface_session, redis_server, app_name)
