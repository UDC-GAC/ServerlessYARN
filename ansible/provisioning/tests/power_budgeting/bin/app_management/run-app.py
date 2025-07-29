
import os
import sys
import time
import stat
import requests
import subprocess
from urllib.parse import urljoin
from celery import Celery
from datetime import datetime, timezone, timedelta

WEB_INTERFACE_URL = "http://localhost:9000"
ORCHESTRATOR_URL = "http://localhost:5000"
BENEVOLENCE = "-1"  # -1: "Manual", 1: "Lax", 2: "Medium", 3: "Strict"
POLLING_FREQUENCY = 20
ACTIVE_TASK_NAMES = ["ui.background_tasks.start_app_task",
                     "ui.background_tasks.start_app_on_container_task",
                     "ui.background_tasks.stop_app_on_container_task",
                     "ui.background_tasks.wait_for_app_on_container_task"]


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


def write_containers_file(exp_results_dir, containers):
    with open(f"{exp_results_dir}/containers", 'a') as f:
        for container in containers:
            f.write(f"{container}\n")


def check_app_task_is_active(inspector, app_name):
    for _, active_tasks in inspector.active().items():
        for task in active_tasks:
            task_name = task.get("name", "")
            if task_name in ACTIVE_TASK_NAMES and app_name in task.get("args", []):
                return True
    return False


def wait_for_app_to_finish(inspector, app_name):
    # TODO: Maybe is better just to wait until a directory with timestamp after now exists, then we know the app has finished
    #       and we have the logs ready
    app_running = True
    while app_running:
        app_running = check_app_task_is_active(inspector, app_name)
        time.sleep(POLLING_FREQUENCY)
        # If the app is not running check one more time to ensure it wasn't a temporary change
        if not app_running:
            app_running = check_app_task_is_active(inspector, app_name)


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


def get_closest_dir_by_date(dir_list, dir_format="%Y-%m-%d--%H-%M-%S"):
    now = datetime.now()
    min_delta = timedelta(days=30)
    closest_item = None
    for item in dir_list:
        try:
            dt = datetime.strptime(item, dir_format)
        except ValueError:
            continue
        delta = (now - dt)
        if delta < min_delta:
            min_delta = delta
            closest_item = item
    return closest_item


def copy_app_output(containers, installation_path, app_name, exp_results_dir):
    app_output_dir = f"{installation_path}/output_data/{app_name}/"
    execution_dir = get_closest_dir_by_date(os.listdir(app_output_dir))

    # Copy each container output
    for container in containers:
        container_output_dir = f"{app_output_dir}/{execution_dir}/output_dir-{container}"
        container_results_dir = f"{exp_results_dir}/{container}-output"
        # Search for some output directory in the container bind dir
        if os.path.isdir(container_output_dir) and os.path.exists(container_output_dir):
            copy_directory(container_output_dir, container_results_dir)
        else:
            print(f"Container output directory doesn't exist: {container_output_dir}")


def get_pb_script_with_usr_perm(installation_path):
    file = f"{installation_path}/ServerlessContainers/scripts/orchestrator/Structures/set_structure_energy_max.sh"
    current_permissions = os.stat(file).st_mode
    new_permissions = current_permissions | stat.S_IXUSR  # Add permissions for this user
    os.chmod(file, new_permissions)  # Change file permissions

    return file, current_permissions


def change_power_budgets_dynamically(app_name, containers, power_budgets, exp_results_dir, installation_path):
    power_budgets_file = f"{exp_results_dir}/power_budgets.log"
    change_pb_script, original_permissions = get_pb_script_with_usr_perm(installation_path)
    if len(containers) == 1:
        # Power budget is applied at container-level in single-container applications as no rebalancing is done
        run_args = [change_pb_script, containers[0]]
    else:
        run_args = [change_pb_script, app_name]
    if power_budgets:
        for i, pb_item in enumerate(power_budgets):
            pb, wait_time = tuple(pb_item.split("-"))
            time.sleep(int(wait_time))
            try:
                rc = subprocess.Popen(run_args + [pb], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S+0000')
                out, err = rc.communicate()
                if rc.returncode != 0:
                    raise Exception(err.decode('utf-8'))

                # Save timestamp of the power budget change
                with open(power_budgets_file, 'a') as f:
                    f.write(f"[{timestamp}] {pb}\n")
            except Exception as e:
                print(f"Error changing power budget of app {app_name} to {pb} W "
                      f"using script {change_pb_script}: {str(e)}")
    else:
        print("There is no defined power budget")

    os.chmod(change_pb_script, original_permissions)  # Reset original permissions


if __name__ == "__main__":

    if len(sys.argv) < 5:
        print("At least 4 arguments are needed")
        print("1 -> app name (e.g., npb_app)")
        print("2 -> experiment results directory (e.g., ./out/npb_app/exp1)")
        print("3 -> number of containers (e.g., 1)")
        print("4 -> assignation policy (e.g., Best-effort)")
        sys.exit(1)

    app_name = sys.argv[1]
    exp_results_dir = sys.argv[2]
    number_of_containers = sys.argv[3]
    assignation_policy = sys.argv[4]

    dynamic_pb = False
    dynamic_power_budgets = None
    if len(sys.argv) >= 6:
        dynamic_pb = True
        dynamic_power_budgets = sys.argv[5].split(",")

    installation_path = os.environ.get("SC_YARN_PATH", f"{os.environ.get('HOME')}/ServerlessYARN_install")
    celery_client = Celery("client", broker="redis://localhost:6379/0", backend="redis://localhost:6379/0")
    celery_inspector = celery_client.control.inspect()

    web_interface_session = requests.Session()
    orchestrator_session = requests.Session()

    # Run application
    start_app(web_interface_session, app_name, number_of_containers, assignation_policy)
    time.sleep(60)  # Wait some time for the app to be subscribed to SC

    # Get containers subscribed to the application and register them into a file
    containers = get_containers_from_app(orchestrator_session, app_name)
    write_containers_file(exp_results_dir, containers)

    # Change power budget in real time
    if dynamic_pb:
        change_power_budgets_dynamically(app_name, containers, dynamic_power_budgets, exp_results_dir, installation_path)

    # Wait until the app is finished
    wait_for_app_to_finish(celery_inspector, app_name)

    # When app is finished copy its output
    copy_app_output(containers, installation_path, app_name, exp_results_dir)
