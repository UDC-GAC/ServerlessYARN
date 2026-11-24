import time
import json
import timeit
import yaml
import uuid
import redis
import urllib
import subprocess
from contextlib import contextmanager

from celery import shared_task, group
from celery.result import AsyncResult

from django.conf import settings

from serverless_containers_web.celery import app as celery_app
from serverlessyarn_utils.web_utils import web_request

from ui.domain.state_db import getDbData, getDataAndFilterByApp
from ui.domain.structures import getHostsNames
from ui.domain.placement import getContainerAssignationForApp
from ui.domain.update_inventory_file import add_containers_to_hosts, remove_container_from_host, add_host, remove_host, add_disks_to_hosts
import ui.domain.run_playbooks as run_playbooks
from ui.bigdata.data_locality import get_data_locality_scores

config_path = "../../config/config.yml"
with open(config_path, "r") as config_file: config = yaml.load(config_file, Loader=yaml.FullLoader)

redis_server = redis.StrictRedis()
redis_prefix = "pending_tasks"
lock_key = "ansible_inventory_access_lock"

## Celery tasks managing
def register_task(task_id, task_name):
    key = "{0}:{1}".format(redis_prefix,task_id)
    redis_server.hset(key, "task_name", task_name)

def create_artificial_task(task_name, status, result=None):
    ## 1: create fake task that represents the work task
    task_id = str(uuid.uuid4())
    celery_app.backend.store_result(
        task_id=task_id,
        result=result,
        state=status.upper()
    )
    ## 2: register wrapper pending task
    register_task(task_id, task_name)

    return task_id

def update_task_runtime(task_id, runtime):
    key = "{0}:{1}".format(redis_prefix,task_id)
    redis_server.hset(key, "runtime", runtime)

def remove_task(task_id):
    redis_server.delete("{0}:{1}".format(redis_prefix, task_id))

def remove_task_by_name(task_name):
    for key in redis_server.scan_iter("{0}:*".format(redis_prefix)):
        stored_task_name = redis_server.hget(key, "task_name")
        if stored_task_name and stored_task_name.decode("utf-8") == task_name:
            task_id = key.decode("utf-8")[len(redis_prefix) + 1:]
            if task_id:
                remove_task(task_id)
                return

def get_pending_tasks():
    still_pending_tasks = []
    successful_tasks = []
    failed_tasks = []

    for key in redis_server.scan_iter("{0}:*".format(redis_prefix)):
        task_name = redis_server.hget(key, "task_name")
        task_name = "None" if task_name is None else task_name.decode("utf-8")
        task_id = key.decode("utf-8")[len(redis_prefix) + 1:]
        task_result = AsyncResult(task_id)
        status = task_result.status ## the 'status' attribute is an alias for 'state', i.e., both have the same value

        if status != "SUCCESS" and status != "FAILURE":
            still_pending_tasks.append((task_id,task_name))
        elif status == "SUCCESS":
            if redis_server.hexists(key, "runtime"):
                runtime = redis_server.hget(key, "runtime").decode("utf-8")
            else:
                runtime = None
            successful_tasks.append((task_id,task_name,runtime))
        else:
            failed_tasks.append((task_id,task_name,task_result.result))

    # remove completed or failed tasks
    for task_id, task_name, runtime in successful_tasks:
        redis_server.delete(f"{redis_prefix}:{task_id}")
        redis_server.delete(f"celery-task-meta-{task_id}")

    for task_id, task_name, task_error in failed_tasks:
        redis_server.delete(f"{redis_prefix}:{task_id}")
        redis_server.delete(f"celery-task-meta-{task_id}")

    return still_pending_tasks, successful_tasks, failed_tasks

def get_pending_tasks_messages():
    still_pending_tasks, successful_tasks, failed_tasks = get_pending_tasks()

    still_pending_tasks_string = []
    successful_tasks_string = []
    failed_tasks_string = []

    for task_id, task_name in still_pending_tasks:
        info = "Task with ID {0} and name {1} is pending".format(task_id,task_name)
        still_pending_tasks_string.append({"id": task_id, "message": info})

    for task_id, task_name, runtime in successful_tasks:
        if runtime != None: runtime_str = " in {0} seconds".format(runtime)
        else: runtime_str = ""
        success = "Task with ID {0} and name {1} has completed successfully{2}".format(task_id,task_name,runtime_str)
        successful_tasks_string.append({"id": task_id, "message": success})

    for task_id, task_name, task_error in failed_tasks:
        error = "Task with ID {0} and name {1} has failed with error: {2}".format(task_id,task_name,task_error)
        failed_tasks_string.append({"id": task_id, "message": error})

    return still_pending_tasks_string, successful_tasks_string, failed_tasks_string

def create_app_counter(app_name, initial_value):
    task_id = f"app:{app_name}"
    redis_server.hset(task_id, "active_containers", initial_value)

def get_app_counter(app_name):
    task_id = f"app:{app_name}"
    return redis_server.hget(task_id, "active_containers").decode("utf-8")

def remove_app_counter(app_name):
    task_id = f"app:{app_name}"
    redis_server.delete(task_id)

## Auxiliary
def container_list_to_formatted_str(container_list):
    return str(container_list).replace('[','').replace(']','').replace(', ',',').replace('\'','')

def mergeDictionary(dict_1, dict_2):
   dict_3 = {**dict_2, **dict_1}
   for key, value in dict_3.items():
       if key in dict_1 and key in dict_2:
               dict_3[key] = value + dict_2[key]
   return dict_3

def convert_strings_to_numbers(data):
    """
    Recursively convert string numbers to int/float in nested dictionaries and lists.
    """
    if isinstance(data, dict):
        return {key: convert_strings_to_numbers(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_strings_to_numbers(item) for item in data]
    elif isinstance(data, str):
        # Try to convert to int first, then float
        try:
            return int(data)
        except ValueError:
            try:
                return float(data)
            except ValueError:
                return data
    else:
        return data

def manage_scaling_services(enable, skip_ansible=True):
    if skip_ansible:
        sc_path = "{0}/ServerlessContainers".format(settings.INSTALLATION_PATH)
        services = ["Scaler", "Guardian", "Rebalancer"] + (["EnergyController"] if settings.PLATFORM_CONFIG["power_budgeting"] else [])
        script = "activate.sh" if enable else "deactivate.sh"

        # Deactivate services in parallel
        processes = []
        for service in services:
            p = subprocess.Popen(["bash", f"{sc_path}/scripts/orchestrator/{service}/{script}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append((service, p))

        # Wait for output to check there is no errors
        for service, p in processes:
            out, err = p.communicate()
            print("{0} {1} using local scripts: {2}".format("Activating" if enable else "Deactivating", service, out.decode("utf-8")))
            if p.returncode != 0:
                extracted_error = err.decode("utf-8")
                if extracted_error.strip() == "":
                    extracted_error = "Please consult Celery log under services/celery for further details"
                raise Exception("Error managing scaling service {0} (enable={1}): {2}".format(service, enable, extracted_error))
    else:
        run_playbooks.manage_scaling_services(enable=enable)

@contextmanager
def scaling_services_disabled():
    manage_scaling_services(enable=False)
    try:
        yield
    finally:
        manage_scaling_services(enable=True)


## Adds
@shared_task
def add_host_task(host,cpu,mem,disk_info,energy,new_containers):

    # update_inventory_file
    with redis_server.lock(lock_key):
        add_host(host,cpu,mem,disk_info,energy,new_containers)

    run_playbooks.configure_host(host)

def getHostsInfo(url):

    response = urllib.request.urlopen(url)
    data_json = json.loads(response.read())

    hosts = {}

    for item in data_json:
        if (item['subtype'] == 'host'):

            hosts[item["name"]] = item

    return hosts

@shared_task
def extend_lv_task(host_names, new_disks, extra_disk, measure_host_list, throttle_containers_bw=False):
    run_playbooks.extend_lv(host_names, new_disks, extra_disk, measure_host_list, throttle_containers_bw=throttle_containers_bw)

@shared_task
def add_disks_to_hosts_task(host_list, add_to_lv, new_disks, extra_disk, measure_host_list, structures_url, threshold, polling_frequency, timeout_events):

    # update_inventory_file
    with redis_server.lock(lock_key):
        added_disks = add_disks_to_hosts(host_list,new_disks)

    if add_to_lv:
        ## Add disks to existing LV
        ## 1st, extend LVs with no containers, so inmediate benchmark can be run on them
        for host in measure_host_list:
            if measure_host_list[host]:
                task = extend_lv_task.delay([host], ",".join(new_disks), extra_disk, str(measure_host_list).replace(' ',''))
                register_task(task.id, "extend_lv_task")
                host_list.remove(host)

        ## 2nd, remaining hosts have containers. Pool their consumed bandwidth to check if they can be extended
        current_events = 0
        while current_events < timeout_events and len(host_list) > 0:
            finished_hosts = []
            hosts_full_info = getHostsInfo(structures_url) # refresh host info
            for host in host_list:
                # get host free bandwidth
                host_max_read_bw = hosts_full_info[host]["resources"]["disks"]["lvm"]["max_read"]
                host_max_write_bw = hosts_full_info[host]["resources"]["disks"]["lvm"]["max_write"]
                host_free_read_bw = hosts_full_info[host]["resources"]["disks"]["lvm"]["free_read"]
                host_free_write_bw = hosts_full_info[host]["resources"]["disks"]["lvm"]["free_write"]
                consumed_read = host_max_read_bw - host_free_read_bw
                consumed_write = host_max_write_bw - host_free_write_bw
                total_free_bw = max(host_max_read_bw, host_max_write_bw) - consumed_read - consumed_write
                # compare bw with threshold
                if (max(host_max_read_bw, host_max_write_bw) - total_free_bw <= max(host_max_read_bw, host_max_write_bw) * threshold
                    and host_max_read_bw  - host_free_read_bw  <= host_max_read_bw  * threshold
                    and host_max_write_bw - host_free_write_bw <= host_max_write_bw * threshold
                    ):
                    ## enough free bandwidth to execute benchmark anyways
                    task = extend_lv_task.delay([host], ",".join(new_disks), extra_disk, str(measure_host_list).replace(' ',''))
                    register_task(task.id, "extend_lv_task")
                    finished_hosts.append(host)
                else:
                    ## consumed bandwidth over the threshold, extend postponed
                    pass

            host_list = [host for host in host_list if host not in finished_hosts]
            current_events += 1
            if current_events < timeout_events and len(host_list) > 0:
                time.sleep(polling_frequency)


        ## if timeout_events == -1 -> execute extension without limiting (?)

        ## 3rd, hosts that were not able to reduce bandwidth under the threshold; will extend lv regardless, but capping the available bandiwdth of their containers
        if len(host_list) > 0:
            run_playbooks.extend_lv(host_list, new_disks, extra_disk, str(measure_host_list).replace(' ',''), throttle_containers_bw=True)

    else:
        ## Add disks just as new individual disks
        formatted_added_disks = str(added_disks).replace(' ','')
        run_playbooks.add_disks(host_list, formatted_added_disks)

@shared_task
def add_app_task(full_url, put_field_data, app, app_files, user=None):
    error_message = "Error adding app {0}".format(app)
    error, _ = web_request(full_url, "put", error_message, put_field_data)

    if not error:
        run_playbooks.create_app(app_files)
    else:
        raise Exception(error)

    # If a user is specified subscribe app to user
    if user and user != "":
        parsed_url = urllib.parse.urlparse(full_url)
        user_url = "{0}://{1}/user/clusters/{2}/{3}".format(parsed_url.scheme, parsed_url.netloc, user, app)
        manage_app_with_user_in_db(user_url, app, user, "put")

@shared_task
def add_user_task(full_url, put_field_data, user):
    error_message = "Error adding user {0}".format(user)
    error, _ = web_request(full_url, "put", error_message, put_field_data)
    if error:
        raise Exception(error)

@shared_task
def subscribe_apps_to_user(url, user_name, user_apps):
    with scaling_services_disabled():
        # Subscribe containers to app in ServerlessContainers database
        for app_name in user_apps:
            full_url = url + "clusters/{0}/{1}".format(user_name, app_name)
            manage_app_with_user_in_db(full_url, user_name, app_name, "put")

@shared_task
def desubscribe_apps_from_user(url, user_name, user_apps):
    with scaling_services_disabled():
        # Subscribe containers to app in ServerlessContainers database
        for app_name in user_apps:
            full_url = url + "clusters/{0}/{1}".format(user_name, app_name)
            manage_app_with_user_in_db(full_url, user_name, app_name, "delete")

def change_app_state_in_db(url, app, state):
    max_retries = 10
    actual_try = 0
    full_url = f"{url}{app}/state/{state}"
    while actual_try < max_retries:

        error_message = "Error changing app {0} execution state to {1}".format(app, state)
        error, response = web_request(full_url, "put", error_message)

        if response != "":
            if not error: break
            else: raise Exception(error)

        actual_try += 1

    if actual_try >= max_retries:
        raise Exception("Reached max tries when changing app {0} execution state to {1}".format(app, state))

def enable_container_guard_in_db(url, container_name):
    max_retries = 10
    actual_try = 0
    full_url = f"{url}{container_name}/guard"
    while actual_try < max_retries:

        error_message = "Error enabling guard for container {0}".format(container_name)
        error, response = web_request(full_url, "put", error_message)

        if response != "":
            if not error: break
            else: raise Exception(error)

        actual_try += 1

    if actual_try >= max_retries:
        raise Exception("Reached max tries when enabling guard for container {0}".format(container_name))

def add_container_to_app_in_db(full_url, container, app):
    max_retries = 10
    actual_try = 0

    while actual_try < max_retries:

        error_message = "Error adding container {0} to app {1}".format(container, app)
        error, response = web_request(full_url, "put", error_message)

        if response != "":
            if not error: break
            elif response.status_code == 400 and "already subscribed" in error: break # Container is already subscribed
            else: raise Exception(error)

        actual_try += 1

    if actual_try >= max_retries:
        raise Exception("Reached max tries when adding {0} to app {1}".format(container, app))

def manage_app_with_user_in_db(full_url, app, user, operation):
    max_retries = 10
    actual_try = 0

    while actual_try < max_retries:

        error_message = "Error adding app {0} to user {1}".format(app, user)
        error, response = web_request(full_url, operation, error_message)

        if response != "":
            if not error:
                break
            if response.status_code == 400:
                if "already subscribed" in error or "missing in" in error: # App is already subscribed/desubscribed
                    break
            raise Exception(error)

        actual_try += 1

    if actual_try >= max_retries:
        raise Exception("Reached max tries when adding {0} to user {1}".format( app, user))

@shared_task
def wait_for_app_on_container_task(host, container, app):
    run_playbooks.wait_for_app_on_container(host, container['container_name'])


@shared_task
def start_app_on_container_task(full_url, host, container, app, app_files, global_hdfs_data=None):
    bind_path = ""
    if 'disk_path' in container:
        bind_path = container['disk_path']

    run_playbooks.start_app_on_container(host, container['container_name'], app, app_files, bind_path, global_hdfs_data)

## Start containers
@shared_task
def start_containers_task_v2(new_containers, container_resources, disks):

    # update inventory file
    with redis_server.lock(lock_key):
        added_containers = add_containers_to_hosts(new_containers)

    containers_info = []
    for host in added_containers:
        for container in added_containers[host]:
            container_info = {}
            container_info['container_name'] = container
            container_info['host'] = host
            # Resources
            for resource in ['cpu', 'mem', 'disk_read', 'disk_write', 'energy']:
                for key in ['max', 'min', 'weight', 'boundary', 'boundary_type']:
                    resource_key = '{0}_{1}'.format(resource, key)
                    if resource_key in container_resources:
                        container_info[resource_key] = container_resources[resource_key]

            if len(disks) > 0:
                container_info['disk'] = disks[host]['name']
                container_info['disk_path'] = "/".join([disks[host]['path'], settings.VARS_CONFIG['bind_dir_name'], container])

            containers_info.append(container_info)

    if len(containers_info) == 0:
        # Nothing to do
        return

    formatted_containers_info = str(containers_info).replace(' ','')
    run_playbooks.start_containers(list(added_containers.keys()), formatted_containers_info)


def deploy_app_containers(url, new_containers, app, app_files, container_resources, disk_assignation, app_type=None):

    added_containers = {}

    # Add containers to hosts in Ansible inventory
    with redis_server.lock(lock_key):
        for host in new_containers:
            added_containers[host] = {}
            for container_type in ['master','irregular','regular']:
                if container_type in new_containers[host]:
                    added_containers[host][container_type] = add_containers_to_hosts({host: new_containers[host][container_type]})[host]

    # Format containers info to use in Ansible playbooks
    containers_info = []
    for host in added_containers:
        for container_type in ['master', 'irregular', 'regular']:
            if container_type in added_containers[host]:
                for container in added_containers[host][container_type]:
                    container_info = {}
                    container_info['container_name'] = container
                    container_info['host'] = host
                    container_info['guard'] = "false" ## containers are not allowed to scale until the app has actually started running
                    # Resources
                    for resource in ['cpu', 'mem']:
                        for key in ['max', 'min', 'weight', 'boundary', 'boundary_type']:
                            resource_key = "{0}_{1}".format(resource, key)
                            container_info[resource_key] = container_resources[container_type][resource_key]

                    # Energy
                    if config['power_budgeting']:
                        for resource in ['energy_max', 'energy_min', 'energy_weight', 'energy_boundary', 'energy_boundary_type']:
                            container_info[resource] = container_resources[container_type][resource]

                    # Disks
                    if config['disk_capabilities'] and config['disk_scaling'] and container_type != 'master':
                        for disk in disk_assignation[host]:
                            if disk_assignation[host][disk]['new_containers'] > 0:
                                disk_assignation[host][disk]['new_containers'] -= 1
                                container_info['disk'] = disk
                                container_info['disk_path'] = "/".join([disk_assignation[host][disk]['disk_path'], settings.VARS_CONFIG['bind_dir_name'], container])
                                for resource in ['disk_read', 'disk_write']:
                                    for key in ['max', 'min', 'weight', 'boundary', 'boundary_type']:
                                        resource_key = "{0}_{1}".format(resource,key)
                                        container_info[resource_key] = container_resources[container_type][resource_key]

                                break

                    containers_info.append(container_info)

    if len(containers_info) == 0:
        # Nothing to do
        return

    formatted_containers_info = str(containers_info).replace(' ', '')

    # Deploy containers through Ansible
    with scaling_services_disabled():
        try:
            run_playbooks.start_containers_with_app(list(added_containers.keys()), formatted_containers_info, app, app_type, app_files)
        except Exception as e:
            ## Ensure containers are removed from inventory and instances are stopped in case of failure
            for container in containers_info:
                stop_container(container["host"], container["container_name"])

            ## Ensure app is stopped
            change_app_state_in_db(url, app, "stopped")

            ## Then, throw the original exception as the start app process must stop here
            raise e

    return containers_info


## Start Apps
def wait_for_app_dependency(assignation_requirements, url, app, container_resources, dependencies):

    def check_space_for_app(assignation_requirements, url, container_resources, app_name):

        container_resources = convert_strings_to_numbers(container_resources)

        app_resources = assignation_requirements['app_resources']
        assignation_policy = assignation_requirements['assignation_policy']
        allow_oversubscription = assignation_requirements['allow_oversubscription']
        number_of_containers = assignation_requirements['number_of_containers']
        allocation_exclusions = assignation_requirements['allocation_exclusions']

        # Get updated info about hosts
        data_json = getDbData(url)
        hosts = getHostsNames(data_json)

        # Check if there is space for app
        ## Note: this simply checks whether there are enough resources for the app across all hosts to ensure no unreasonable requests are being made
        ## allocation may still fail when trying to assign each container to a host
        free_resources = {}
        for resource in app_resources:
            free_resources[resource] = 0

        for host in hosts:
            ## Regular resources
            for resource in set(free_resources.keys()) - {'disk_read', 'disk_write'}:
                free_resources[resource] += host['resources'][resource]['free']

            ## Disk
            check_disks = settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling']
            if check_disks and 'disks' in host['resources']:

                ### Remove reserved disks
                if host['name'] in allocation_exclusions and 'disks' in allocation_exclusions[host['name']]:
                    host['resources']['disks'] = {disk: disk_data for disk, disk_data in host['resources']['disks'].items() if disk not in allocation_exclusions[host['name']]['disks']}

                for disk in host['resources']['disks']:
                    for op in ['read', 'write']:
                        if f'disk_{op}' in free_resources:
                            free_resources[f'disk_{op}'] += host['resources']['disks'][disk][f'free_{op}']

        if any(free_resources[resource] < app_resources[resource]['min'] - app_resources[resource]['current'] for resource in free_resources):
            raise Exception("There is no capacity for app {0}. Requested resources: {1}. Free resources: {2}".format(app_name, app_resources, free_resources))

        # Locate the data the app will read (done after waiting for the dependency, as it may produce the input data of this app)
        locality_scores = None
        if assignation_policy == "Data-locality":
            locality_scores, locality_source = get_data_locality_scores(app_name, assignation_requirements['data_locality'], dependencies.get("app"))
            print("[DATA LOCALITY] Locality scores for app {0} based on {1}: {2}".format(app_name, locality_source, locality_scores))
            ## Keep the source of the scores to store it in the deployment registry later
            assignation_requirements['data_locality']['source'] = locality_source

        # Allocate the containers for each host
        new_containers, disk_assignation, error = getContainerAssignationForApp(assignation_policy, allow_oversubscription, hosts, number_of_containers, container_resources, app_name, locality_scores)
        if error != "":
            raise Exception(error)

        return new_containers, disk_assignation

    if dependencies:
        ## Check app dependency state
        polling_period = 1
        _, dependency_app = getDataAndFilterByApp(url, dependencies["app"])
        continue_condition = any(dependency_app["state"] == condition for condition in dependencies["conditions"])

        if not continue_condition:
            while not continue_condition:
                time.sleep(polling_period)
                _, dependency_app = getDataAndFilterByApp(url, dependencies["app"])
                continue_condition = any(dependency_app["state"] == condition for condition in dependencies["conditions"])

            time.sleep(60) ## wait a bit before running app if the dependency condition was just met

    new_containers, disk_assignation = check_space_for_app(assignation_requirements, url, container_resources, app)

    return new_containers, disk_assignation

def rollback_start_flow(url, app, app_containers, app_files):
    if app_containers:
        try:
            errors = stop_app_on_containers(app, app_files, app_containers)
        except Exception as e:
            errors = [str(e)]
        for error in errors:
            print("[ROLLBACK] {0}".format(error))

        for container in app_containers:
            try:
                full_url = url + "container/{0}/{1}".format(container['container_name'], app)
                remove_container_from_app_db(full_url, container['container_name'], app)
            except Exception as e:
                print("[ROLLBACK] Error removing container {0} from StateDatabase: {1}".format(container['container_name'], str(e)))

    try:
        change_app_state_in_db(url, app, "stopped")
    except Exception as e:
        print("[ROLLBACK] Error changing application {0} state to stopped: {1}".format(app, str(e)))

    try:
        manage_scaling_services(enable=True)
    except Exception as e:
        print("[ROLLBACK] Error changing enabling Scaler: {0}".format(str(e)))


@shared_task(bind=True)
def start_app_task(self, assignation_requirements, url, app, app_files, container_resources, scaler_polling_freq, app_type=None, dependencies={}):

    new_containers, disk_assignation = wait_for_app_dependency(assignation_requirements, url, app, container_resources, dependencies)

    if settings.PLATFORM_CONFIG['enable_app_callback']:
        ## Create redis counter to track the containers' status
        create_app_counter(app, assignation_requirements['number_of_containers'])

    start_time = timeit.default_timer()

    # Set application in running state in ServerlessContainers
    change_app_state_in_db(url, app, "running")

    app_containers = None
    try:
        # Deploy all the containers in the remote hosts
        app_containers = deploy_app_containers(url, new_containers, app, app_files, container_resources, disk_assignation, app_type)

        # Setup containers network to enable communications between containers
        setup_containers_network_task(url, app, app_containers, new_containers)

        # Start app inside all the containers
        start_app_on_containers(url, app, app_containers, app_files)

    except Exception as e:
        rollback_start_flow(url, app, app_containers, app_files)
        raise e

    if not settings.PLATFORM_CONFIG['enable_app_callback']:
        # Wait for app to finish in all the containers
        wait_for_app_on_containers(app, app_containers)

        end_time = timeit.default_timer()
        runtime = "{:.2f}".format(end_time-start_time)
        update_task_runtime(self.request.id, runtime)

        # Destroy all the containers and remove them from ServerlessContainers
        remove_containers_from_app(url, app_containers, app, app_files)

@shared_task
def setup_containers_network_task(url, app, app_containers, new_containers):
    # Setup networks for a group of containers belonging to the same app
    # app_containers example = [{'container_name':'host1-cont0','host':'host1','cpu_max':200,'disk':'ssd_0',...},{'container_name':'host2-cont0','host':'host2',...}]
    formatted_app_containers = str(app_containers).replace(' ', '')
    run_playbooks.setup_network_on_containers(list(new_containers.keys()), formatted_app_containers, app)

@shared_task
def subscribe_containers_to_app(url, app, app_containers):
    with scaling_services_disabled():
        # Subscribe containers to app in ServerlessContainers database
        for container in app_containers:
            full_url = url + "container/{0}/{1}".format(container['container_name'], app)
            add_container_to_app_in_db(full_url, container['container_name'], app)

@shared_task
def wait_for_app_on_containers(app, app_containers):
    # Create a task for each container in charge of starting the app inside them
    tasks = []
    for container in app_containers:
        wait_task = wait_for_app_on_container_task.si(container['host'], container, app)
        tasks.append(wait_task)

    result = group(tasks)()
    while not result.ready():
        time.sleep(1)
    result.get()


@shared_task
def start_app_on_containers(url, app, app_containers, app_files):
    # Create a task for each container in charge of starting the app inside them
    tasks = []
    for container in app_containers:
        full_url = url + "container/{0}/{1}".format(container['container_name'], app)
        # Containers are allowed to be scaled from now on, as the app is going to start running
        enable_container_guard_in_db(url, container['container_name'])
        start_task = start_app_on_container_task.si(full_url, container['host'], container, app, app_files)
        tasks.append(start_task)

    result = group(tasks)()
    while not result.ready():
        time.sleep(1)
    result.get()


## Removes
@shared_task
def remove_host_task(full_url, host_name):

    error_message = "Error removing host {0}".format(host_name)
    error, _ = web_request(full_url, "delete", error_message)

    ## Remove host
    if not error:
        # Stop node scaler service in host
        run_playbooks.stop_host_scaler(host_name)

        # update inventory file
        with redis_server.lock(lock_key):
            remove_host(host_name)
    else:
        raise Exception(error)

@shared_task
def remove_app_task(url, structure_type_url, app_name, container_list, app_files, user=None):

    errors = []

    # First, remove all containers from app
    if len(container_list) > 0:
        # Containers come from StateDB, so convert them to the same format used when deploying apps
        app_containers = [get_container_deployment_info(container) for container in container_list]
        errors += remove_app_containers_from_db(url, app_name, app_containers)
        errors += stop_app_on_containers(app_name, app_files, app_containers)

    # If app is associated with a user, desubscribe app from user
    if user and user != "":
        full_url = settings.BASE_URL + "/user/clusters/" + user + "/" + app_name + "/"
        error_message = "Error removing app {0} from user {1}".format(app_name, user)
        error, _ = web_request(full_url, "delete", error_message)

        if error:
            errors.append(error)
            raise Exception(str(errors))

    # Then, actually remove app
    error = remove_app_from_db(url, app_name, structure_type_url)
    if error: errors.append(error)

    if len(errors) > 0: raise Exception(str(errors))

@shared_task
def remove_containers_task(url, container_list):

    ## Disable scaler and other scaling services, remove all containers from StateDB and re-enable them
    with scaling_services_disabled():
        # Ensure Scaler finish current iteration and persist host info before removing containers
        # Sleep is not needed because orchestrator will do safe updated
        #time.sleep(scaler_polling_freq)

        errors = []
        for container in container_list:
            full_url = url + "container/{0}".format(container['name'])
            error = remove_container_from_db(full_url, container['name'])
            if error != "": errors.append(error)


    ## Stop Containers
    # Stop and remove containers
    for container in container_list:
        full_url = url + "container/{0}".format(container['name'])
        bind_path = ""
        #if 'disk_path' in container: bind_path = container['disk_path']
        if 'disk' in container['resources'] and 'path' in container['resources']['disk']: bind_path = container['resources']['disk']['path']
        stop_task = stop_container.delay(container['host'], container['name'], bind_path)
        register_task(stop_task.id,"stop_container_task")

    # It would be great to execute tasks on a group, but the group task ID is not trackable

    if len(errors) > 0: raise Exception(str(errors))

@shared_task
def remove_containers_from_app(url, container_list, app, app_files, remove_dns_entries=True):
    # 'remove_dns_entries' should be disabled when just a subset of the app containers is removed, as the app DNS entries are still needed

    # Set app as stopped and desubscribe containers from app in StateDB
    errors = remove_app_containers_from_db(url, app, container_list, app_state="stopped")

    # Stop app on containers (persisting output data) and stop containers on remote hosts
    errors += stop_app_on_containers(app, app_files, container_list, remove_dns_entries=remove_dns_entries)

    if len(errors) > 0:
        for error in errors: print(error)
        raise Exception(str(errors))

@shared_task
def remove_users_task(url, users):
    with scaling_services_disabled():
        errors = []
        for user_name in users:
            full_url = "{0}/{1}".format(url, user_name)
            error_message = "Error removing user {0}".format(user_name)
            error, _ = web_request(full_url, "delete", error_message)
            if error != "":
                errors.append(error)

    if len(errors) > 0:
        raise Exception(str(errors))

def remove_container_from_db(full_url, container_name):

    # Remove container from DB
    error_message = "Error removing container {0}".format(container_name)
    error, _ = web_request(full_url, "delete", error_message)

    return error

def remove_container_from_app_db(full_url, container_name, app):

    max_retries = 10
    actual_try = 0
    error = ""

    ## Ensure that container is deleted from app
    while actual_try < max_retries:

        # Remove container from app
        error_message = "Error removing container {0} from app {1}".format(container_name, app)
        error, response = web_request(full_url, "delete", error_message)

        if response != "":
            if not error: break
            elif response.status_code == 400 and "missing in app" in error: break # Container was already removed from app
            else: break

        actual_try += 1

    if actual_try >= max_retries:
        error = "Reached max tries when removing {0} from app {1}".format(container_name, app)

    # Remove the container itself
    remove_error = remove_container_from_db(full_url[:full_url.rfind('/')], container_name)
    if remove_error: error = remove_error

    return error

@shared_task
def stop_container(host, container_name, bind_path=None, clean_bind_dir=True):
    error_msg = ""
    try:
        ## Stop container on remote host
        run_playbooks.stop_container(host, container_name, bind_path, clean_bind_dir)
    except Exception as e:
        error_msg += "Error removing container {0} from remote host {1}: {2}".format(container_name, host, str(e))
    try:
        # update inventory file
        with redis_server.lock(lock_key):
            remove_container_from_host(container_name, host)
    except Exception as e:
        error_msg += "\nError removing container {0} from inventory: {1}".format(container_name, str(e))

    if error_msg:
        raise Exception(error_msg)


@shared_task
def stop_app_on_container_task(host, container_name, bind_path, app, app_files, master_container, timestamp=None, download_time=0, upload_time=0, clean_bind_dir=True):
    error_msg = ""
    try:
        ## Run stop script and persist output data
        run_playbooks.stop_app_on_container(host, container_name, app, app_files, master_container, bind_path, timestamp, download_time, upload_time)
    except Exception as e:
        error_msg = "Error stopping application {0} inside container {1}: {2}".format(app, container_name, str(e))
        ## The container is stopped anyway so it is not left running, but its bind directory is kept to avoid losing non-persisted output data
        clean_bind_dir = False
    try:
        stop_container(host, container_name, bind_path, clean_bind_dir)
    except Exception as e:
        error_msg += ("\n" if error_msg else "") + str(e) # Error is already formatted inside stop_container

    if error_msg:
        raise Exception(error_msg)


## Stop workflows
def get_container_deployment_info(container):
    """
    Convert a container retrieved from StateDB (e.g., {'name': ..., 'host': ..., 'resources': {'disk': {'path': ...}}})
    to the format used when deploying apps (e.g., {'container_name': ..., 'host': ..., 'disk_path': ...}).
    """
    if 'container_name' in container:
        return container
    return {
        'container_name': container['name'],
        'host': container['host'],
        'disk_path': container.get('resources', {}).get('disk', {}).get('path', '')
    }

def wait_for_tasks(tasks, polling_period=1):
    """
    Wait for a list of already dispatched tasks to finish and return the errors raised by them.
    Results are not retrieved through AsyncResult.get(), as Celery does not allow waiting for subtasks that way within a task.
    """
    while not all(task.ready() for task in tasks):
        time.sleep(polling_period)
    return [str(task.result) for task in tasks if task.failed()]

def remove_app_from_db(url, app, structure_type_url="apps"):
    full_url = url + structure_type_url + "/" + app
    error_message = "Error removing app {0}".format(app)
    error, _ = web_request(full_url, "delete", error_message)
    return error

def remove_app_containers_from_db(url, app, app_containers, scaler_polling_freq=0, app_state=None):
    """
    Remove the app containers from StateDB while scaling services are disabled, and then optionally change the app state.
    If 'scaler_polling_freq' is set, wait at least that time before re-enabling the scaling services.
    """
    errors = []
    with scaling_services_disabled():
        start_time = timeit.default_timer()
        for container in app_containers:
            full_url = url + "container/{0}/{1}".format(container['container_name'], app)
            error = remove_container_from_app_db(full_url, container['container_name'], app)
            if error != "": errors.append(error)

        ## Wait at least for the scaler polling frequency time before re-enabling it
        elapsed_time = timeit.default_timer() - start_time
        if scaler_polling_freq > elapsed_time:
            time.sleep(scaler_polling_freq - elapsed_time)

        if app_state:
            change_app_state_in_db(url, app, app_state)

    return errors

def stop_app_on_containers(app, app_files, app_containers, master_container="", download_time=0, upload_time=0, keep_bind_dir=None, remove_dns_entries=True):
    """
    Common stop workflow for the containers of any app (generic, Hadoop or global HDFS). In parallel, for each container:
      - Run the app stop script (if any)
      - Persist its output data (if any), including Hadoop logs for Hadoop-based apps
      - Stop the container and remove its bind directory (unless the container is included in 'keep_bind_dir')
    Once all the containers are stopped, the app DNS entries are removed just once.
    'app_containers' must follow the format used when deploying apps (check get_container_deployment_info).
    Returns a list with the errors found.
    """
    if not app_containers: return []
    keep_bind_dir = keep_bind_dir or []

    ## Get timestamp to store output data (shared by all containers)
    timestamp = None
    if app_files.get('output_dir', '') != '':
        timestamp = time.strftime("%Y-%m-%d--%H-%M-%S")

    stop_tasks = []
    for container in app_containers:
        is_master = container['container_name'] == master_container
        stop_task = stop_app_on_container_task.delay(container['host'], container['container_name'], container.get('disk_path', ''),
                                                     app, app_files, master_container, timestamp,
                                                     download_time if is_master else 0, upload_time if is_master else 0,
                                                     clean_bind_dir=container['container_name'] not in keep_bind_dir)
        register_task(stop_task.id, "stop_app_on_container_task")
        stop_tasks.append(stop_task)

    errors = wait_for_tasks(stop_tasks)

    if remove_dns_entries:
        try:
            run_playbooks.remove_app_dns_entries(app_containers[0]['host'], app)
        except Exception as e:
            errors.append("Error removing DNS entries of app {0}: {1}".format(app, str(e)))

    return errors
