import os
import sys
import time
import redis
import requests
from urllib.parse import urljoin
from datetime import datetime, timezone

WEB_INTERFACE_URL = "http://localhost:9000"
ORCHESTRATOR_URL = "http://localhost:5000"
BENEVOLENCE = "-1"  # -1: "Manual", 1: "Lax", 2: "Medium", 3: "Strict"
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


def start_app(session, app_name, number_of_containers, assignation_policy):

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
        "number_of_containers": number_of_containers,
        "assignation_policy": assignation_policy,
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
    tries = 3
    while tries > 0:
        response = session.get(urljoin(ORCHESTRATOR_URL, f"/structure/{app_name}"))
        try:
            if 'containers' in response.json():
                return response.json()['containers']
            else:
                raise Exception(f"No containers found for app {0}: {1}".format(app_name, response.json()))
        except Exception as e:
            print("An error has ocurred while trying to get containers for app {0} from orchestrator: {1}. "
                  "Error:{2}".format(app_name, response, str(e)))
            tries -= 1


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


def copy_file(origin, dest):
    with open(origin, 'rb') as f_o:
        with open(dest, 'wb') as f_d:
            while True:
                chunk = f_o.read(1024)
                if not chunk:
                    break
                f_d.write(chunk)


def copy_directory(origin, dest):
    if not os.path.exists(dest):
        os.makedirs(dest)
    for item in os.listdir(origin):
        origin_item = os.path.join(origin, item)
        dest_item = os.path.join(dest, item)
        if os.path.isdir(origin_item):
            copy_directory(origin_item, dest_item)
        else:
            copy_file(origin_item, dest_item)


def copy_app_output(containers, installation_path, app_results_dir):
    # Copy each container output
    for container in containers:
        container_bind_dir = f"{installation_path}/singularity_binds/{container}/"
        app_output = None
        app_output_dest = None
        # Search for some output directory in the container bind dir
        if os.path.isdir(container_bind_dir) and os.path.exists(container_bind_dir):
            for item in os.listdir(container_bind_dir):
                if "output" in item:
                    app_output = f"{container_bind_dir}/{item}"
                    app_output_dest = f"{app_results_dir}/{container}-{item}"
                    break
        else:
            print(f"Container bind directory doesn't exist: {container_bind_dir}")

        # If some directory including "output" is found, copy
        if app_output and app_output_dest:
            copy_directory(app_output, app_output_dest)


if __name__ == "__main__":

    if len(sys.argv) < 6:
        print("At least 5 arguments are needed")
        print("1 -> app name (e.g., npb_app)")
        print("2 -> containers file (e.g., ./out/containers)")
        print("3 -> app results directory (e.g., ./out/npb_app)")
        print("4 -> number of containers (e.g., 1)")
        print("5 -> assignation policy (e.g., Best-effort)")
        sys.exit(1)

    app_name = sys.argv[1]
    containers_file = sys.argv[2]
    app_results_dir = sys.argv[3]
    number_of_containers = sys.argv[4]
    assignation_policy = sys.argv[5]

    installation_path = os.environ.get("SC_YARN_PATH", f"{os.environ.get('HOME')}/ServerlessYARN_install")

    web_interface_session = requests.Session()
    orchestrator_session = requests.Session()
    redis_server = redis.StrictRedis()

    # Run application
    start_app(web_interface_session, app_name, number_of_containers, assignation_policy)
    time.sleep(60)  # Wait some time for the app to be subscribed to SC
    containers = get_containers_from_app(orchestrator_session, app_name)
    update_containers_file(containers_file, containers)

    # Wait until the app is finished
    wait_for_app_to_finish(web_interface_session, redis_server, app_name)

    # When app is finished copy its output
    copy_app_output(containers, installation_path, app_results_dir)
