import time
import subprocess
from celery import shared_task, chain, chord, group
from celery.result import AsyncResult, allow_join_result
import redis
import json
import timeit
import yaml
import urllib
from django.conf import settings

from ui.update_inventory_file import add_containers_to_hosts,remove_container_from_host, add_host, remove_host, add_disks_to_hosts, add_containers_to_inventory
from ui.utils import request_to_state_db
import ui.run_playbooks as run_playbooks

config_path = "../../config/config.yml"
with open(config_path, "r") as config_file: config = yaml.load(config_file, Loader=yaml.FullLoader)

vars_path = "../../vars/main.yml"
with open(vars_path, "r") as vars_file: vars_config = yaml.load(vars_file, Loader=yaml.FullLoader)

redis_server = redis.StrictRedis()
redis_prefix = "pending_tasks"
lock_key = "ansible_inventory_access_lock"

## Celery tasks managing
def register_task(task_id, task_name):
    key = "{0}:{1}".format(redis_prefix,task_id)
    redis_server.hset(key, "task_name", task_name)

def update_task_runtime(task_id, runtime):
    key = "{0}:{1}".format(redis_prefix,task_id)
    redis_server.hset(key, "runtime", runtime)

def remove_task(task_id):
    redis_server.delete("{0}:{1}".format(redis_prefix, task_id))

def remove_task_by_name(task_name):
    task_id = None
    for key in redis_server.scan_iter("{0}:*".format(redis_prefix)):
        stored_task_name = redis_server.hget(key, "task_name")
        if stored_task_name and stored_task_name.decode("utf-8") == task_name:
            task_id = key.decode("utf-8")[len(redis_prefix) + 1:]
        break

    if task_id:
        remove_task(task_id)

def get_pending_tasks():
    still_pending_tasks = []
    successful_tasks = []
    failed_tasks = []

    for key in redis_server.scan_iter("{0}:*".format(redis_prefix)):
        task_name = redis_server.hget(key, "task_name").decode("utf-8")
        task_id = key.decode("utf-8")[len(redis_prefix) + 1:]
        task_result = AsyncResult(task_id)
        status = task_result.status

        if status != "SUCCESS" and status != "FAILURE":
            still_pending_tasks.append((task_id,task_name))
        elif status == "SUCCESS":
            if redis_server.hexists(key, "runtime"): runtime = redis_server.hget(key, "runtime").decode("utf-8")
            else: runtime = None
            successful_tasks.append((task_id,task_name,runtime))
        else:
            failed_tasks.append((task_id,task_name,task_result.result))

    # remove completed or failed tasks
    for task_id, task_name, runtime in successful_tasks:
        redis_server.delete("{0}:{1}".format(redis_prefix, task_id))

    for task_id, task_name, task_error in failed_tasks:
        redis_server.delete("{0}:{1}".format(redis_prefix, task_id))

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


## Auxiliary
def container_list_to_formatted_str(container_list):
    return str(container_list).replace('[','').replace(']','').replace(', ',',').replace('\'','')

def mergeDictionary(dict_1, dict_2):
   dict_3 = {**dict_2, **dict_1}
   for key, value in dict_3.items():
       if key in dict_1 and key in dict_2:
               dict_3[key] = value + dict_2[key]
   return dict_3

def get_node_reserved_memory(node_memory):
    reserved_memory = 0

    # It will be probably interesting to lower the reserved_memory since the containers do not need that many extra resources

    # < 8 GB
    if node_memory < 8192:
        #reserved_memory = 1024
        reserved_memory = 512
    # 8 GB - 16 GB
    elif node_memory <= 16384:
        reserved_memory = 2048
    # 24 GB
    elif node_memory <= 24576:
        reserved_memory = 4096
    # 48 GB
    elif node_memory <= 49152:
        reserved_memory = 6144
    # 64 GB - 72 GB
    elif node_memory <= 73728:
        reserved_memory = 8192
    # 96 GB
    elif node_memory <= 98304:
        reserved_memory = 12288
    # 128 GB
    elif node_memory <= 131072:
        reserved_memory = 24576
    # > 128 GB
    else:
        reserved_memory = int(node_memory/8)

    return reserved_memory

def get_min_container_size(node_memory):
    min_container_size = 0

    # < 4 GB
    if node_memory < 4096:
        min_container_size = 256
    # 4 GB - 8 GB
    elif node_memory <= 8192:
        min_container_size = 512
    # 8 GB - 24 GB
    elif node_memory <= 24576:
        min_container_size = 1024
    # > 24 GB
    else:
        min_container_size = 2048

    return min_container_size

def set_hadoop_resources(container_resources, virtual_cluster, number_of_workers):

    hadoop_resources = {}

    total_cores = max(int(container_resources["cpu_max"])//100,1)
    min_cores = max(int(container_resources["cpu_min"])//100,1)
    total_memory = int(container_resources["mem_max"])
    total_disks = 1
    heapsize_factor = 0.9

    ## 'Classic' way of calculating resources:
    #reserved_memory = get_node_reserved_memory(total_memory)
    #available_memory = total_memory - reserved_memory
    #min_container_size = get_min_container_size(total_memory)

    #number_of_hadoop_containers = int(min(2*total_cores, 1.8*total_disks, available_memory/min_container_size))
    # mem_per_container = max(min_container_size, available_memory/number_of_hadoop_containers)

    # scheduler_maximum_memory = int(number_of_hadoop_containers * mem_per_container)
    # scheduler_minimum_memory = int(mem_per_container)
    # nodemanager_memory = scheduler_maximum_memory
    # map_memory = scheduler_minimum_memory
    # reduce_memory = int(min(2*mem_per_container, available_memory))
    # mapreduce_am_memory = reduce_memory


    ## 'BDEv' way of calculating resources:
    #number_of_hadoop_containers = int(min(2*total_cores, available_memory/min_container_size))

    if virtual_cluster:
        ## Virtual cluster config (test environment with low resources)
        hyperthreading = False
        app_master_heapsize = 128
        datanode_heapsize = 128
        nodemanager_heapsize = 128
    else:
        ## Physical cluster config (real environment with (presumably) high resources)
        hyperthreading = True
        app_master_heapsize = 1024
        datanode_heapsize = 1024
        nodemanager_heapsize = 1024

    ## adjust total_cores to hyperthreading system
    ## TODO: check if system actually has hyperthreading
    if hyperthreading:
        total_cores = total_cores // 2

    app_master_memory_overhead = int(app_master_heapsize * 0.1)
    if app_master_memory_overhead < 384:
        app_master_memory_overhead = 384
    mapreduce_am_memory = app_master_heapsize + app_master_memory_overhead

    memory_per_container_factor = 0.95
    available_memory = int(total_memory * memory_per_container_factor)
    nodemanager_memory = available_memory - nodemanager_heapsize - datanode_heapsize

    mem_per_container = int((nodemanager_memory - mapreduce_am_memory) / total_cores)

    map_memory_ratio = 1
    reduce_memory_ratio = 1
    map_memory = int(min(mem_per_container * map_memory_ratio, available_memory))
    reduce_memory = int(min(mem_per_container * reduce_memory_ratio, available_memory))

    scheduler_maximum_memory = nodemanager_memory
    #scheduler_minimum_memory = int(mem_per_container)
    scheduler_minimum_memory = 256

    # total_available_memory = 0
    # for host in new_containers:
    #     if container_type in new_containers[host]:
    #         total_available_memory += available_memory * new_containers[host][container_type]
    total_available_memory = available_memory * number_of_workers

    if total_available_memory < map_memory + reduce_memory + mapreduce_am_memory:
        memory_slice = nodemanager_memory/3.5
        scheduler_minimum_memory = int(memory_slice)
        map_memory = scheduler_minimum_memory
        reduce_memory = scheduler_minimum_memory
        mapreduce_am_memory = int(1.5 * memory_slice)

    map_memory_java_opts = int(heapsize_factor * map_memory)
    reduce_memory_java_opts = int(heapsize_factor * reduce_memory)
    #mapreduce_am_memory_java_opts = int(heapsize_factor * mapreduce_am_memory)
    mapreduce_am_memory_java_opts = app_master_heapsize

    hadoop_resources = {
        "vcores": str(total_cores),
        "min_vcores": str(min_cores),
        "scheduler_maximum_memory": str(scheduler_maximum_memory),
        "scheduler_minimum_memory": str(scheduler_minimum_memory),
        "nodemanager_memory": str(nodemanager_memory),
        "map_memory": str(map_memory),
        "map_memory_java_opts": str(map_memory_java_opts),
        "reduce_memory": str(reduce_memory),
        "reduce_memory_java_opts": str(reduce_memory_java_opts),
        "mapreduce_am_memory": str(mapreduce_am_memory),
        "mapreduce_am_memory_java_opts": str(mapreduce_am_memory_java_opts),
        "datanode_heapsize": str(datanode_heapsize),
        "nodemanager_heapsize": str(nodemanager_heapsize)
    }

    # Check assigned resources are valid
    for resource in hadoop_resources:
        value = int(hadoop_resources[resource])
        if value <= 0:
            bottleneck_resource = "CPU" if resource in ["vcores", "min_vcores"] else "memory"
            raise Exception("Error allocating resources for containers in Hadoop application. "
                            "Value for '{0}' is negative ({1}). The application may have been assigned "
                            "too low {2} values.".format(resource, value, bottleneck_resource))

    return hadoop_resources

def extract_hadoop_resources(hadoop_resources):

    resources_to_extract = ["vcores", "min_vcores", "scheduler_maximum_memory", "scheduler_minimum_memory", "nodemanager_memory", 
                            "map_memory", "map_memory_java_opts", "reduce_memory", "reduce_memory_java_opts", "mapreduce_am_memory", 
                            "mapreduce_am_memory_java_opts", "datanode_heapsize", "nodemanager_heapsize"]
    extracted_resources = []

    for resource in resources_to_extract:
        extracted_resources.append(hadoop_resources[resource])

    return extracted_resources

@shared_task
def process_script(script_name, argument_list, error_message):

    rc = subprocess.Popen(["./ui/scripts/{0}.sh".format(script_name), *argument_list], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = rc.communicate()

    # Log ansible output
    print(out.decode("utf-8"))

    if rc.returncode != 0:
        extracted_error = err.decode("utf-8")
        if extracted_error.strip() == "": extracted_error = "Please consult Celery log under services/celery for further details"

        error = "{0}: {1}".format(error_message, extracted_error)
        raise Exception(error)


## Adds
@shared_task
def add_host_task(host,cpu,mem,disk_info,energy,new_containers):

    # update_inventory_file
    with redis_server.lock(lock_key):
        add_host(host,cpu,mem,disk_info,energy,new_containers)

    # argument_list = [host]
    # error_message = "Error adding host {0}".format(host)
    # process_script("configure_host", argument_list, error_message)
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
def add_disks_to_hosts_task(host_list, add_to_lv, new_disks, extra_disk, measure_host_list, structures_url, threshold, polling_frequency, timeout_events):

    # update_inventory_file
    with redis_server.lock(lock_key):
        added_disks = add_disks_to_hosts(host_list,new_disks)

    if add_to_lv:
        ## Add disks to existing LV
        ## 1st, extend LVs with no containers, so inmediate benchmark can be run on them
        for host in measure_host_list:
            if measure_host_list[host]:
                throttle_containers_bw = 0
                # argument_list = [host, ",".join(new_disks), extra_disk, str(measure_host_list).replace(' ',''), str(throttle_containers_bw)]
                # error_message = "Error extending LV of host {0} with disks {1} and extra disk {2}".format(host, str(new_disks), extra_disk)
                # task = process_script.delay("extend_lv", argument_list, error_message)
                task = run_playbooks.extend_lv.delay([host], ",".join(new_disks), extra_disk, str(measure_host_list).replace(' ',''), throttle_containers_bw)
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
                    throttle_containers_bw = 0
                    # argument_list = [host, ",".join(new_disks), extra_disk, str(measure_host_list).replace(' ',''), str(throttle_containers_bw)]
                    # error_message = "Error extending LV of host {0} with disks {1} and extra disk {2}".format(host, str(new_disks), extra_disk)
                    # task = process_script.delay("extend_lv", argument_list, error_message)
                    task = run_playbooks.extend_lv.delay([host], ",".join(new_disks), extra_disk, str(measure_host_list).replace(' ',''), throttle_containers_bw)
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
            throttle_containers_bw = 1
            # argument_list = [','.join(host_list), ",".join(new_disks), extra_disk, str(measure_host_list).replace(' ',''), str(throttle_containers_bw)]
            # error_message = "Error extending LV of hosts {0} with disks {1} and extra disk {2}".format(host_list, str(new_disks), extra_disk)
            # process_script("extend_lv", argument_list, error_message)
            run_playbooks.extend_lv(host_list, new_disks, extra_disk, str(measure_host_list).replace(' ',''), throttle_containers_bw)

    else:
        ## Add disks just as new individual disks
        formatted_added_disks = str(added_disks).replace(' ','')
        # argument_list = [','.join(host_list), formatted_added_disks]
        # error_message = "Error adding disks {0} to hosts {1}".format(str(new_disks), host_list)
        # process_script("add_disks", argument_list, error_message)
        run_playbooks.add_disks(host_list, formatted_added_disks)

@shared_task
def add_app_task(full_url, put_field_data, app, app_files, user=None):
    error_message = "Error adding app {0}".format(app)
    error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)

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
    error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)
    if error:
        raise Exception(error)

@shared_task
def subscribe_apps_to_user(url, user_name, user_apps):
    run_playbooks.disable_scaler()
    run_playbooks.disable_scaling_services()

    # Subscribe containers to app in ServerlessContainers database
    for app_name in user_apps:
        full_url = url + "clusters/{0}/{1}".format(user_name, app_name)
        manage_app_with_user_in_db(full_url, user_name, app_name, "put")

    run_playbooks.enable_scaler()
    run_playbooks.enable_scaling_services()

@shared_task
def desubscribe_apps_from_user(url, user_name, user_apps):
    run_playbooks.disable_scaler()
    run_playbooks.disable_scaling_services()

    # Subscribe containers to app in ServerlessContainers database
    for app_name in user_apps:
        full_url = url + "clusters/{0}/{1}".format(user_name, app_name)
        manage_app_with_user_in_db(full_url, user_name, app_name, "delete")

    run_playbooks.enable_scaler()
    run_playbooks.enable_scaling_services()

def change_app_execution_state_in_db(url, app, state):
    max_retries = 10
    actual_try = 0
    full_url = url + "{0}/{1}".format(app, state)
    while actual_try < max_retries:

        error_message = "Error changing app {0} execution state to {1}".format(app, state)
        error, response = request_to_state_db(full_url, "put", error_message)

        if response != "":
            if not error: break
            else: raise Exception(error)

        actual_try += 1

    if actual_try >= max_retries:
        raise Exception("Reached max tries when adding {0} to app {1}".format(container, app))

def add_container_to_app_in_db(full_url, container, app):
    max_retries = 10
    actual_try = 0

    while actual_try < max_retries:

        error_message = "Error adding container {0} to app {1}".format(container, app)
        error, response = request_to_state_db(full_url, "put", error_message)

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
        error, response = request_to_state_db(full_url, operation, error_message)

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
def start_app_on_container_task(full_url, host, container, app, app_files):
    bind_path = ""
    if 'disk_path' in container:
        bind_path = container['disk_path']

    run_playbooks.start_app_on_container(host, container['container_name'], app, app_files, bind_path)

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
                container_info['disk_path'] = disks[host]['path']
            # # Disks
            # for disk in disk_assignation[host]:
            #     if disk_assignation[host][disk]['new_containers'] > 0:
            #         disk_assignation[host][disk]['new_containers'] -= 1
            #         container_info['disk'] = disk
            #         container_info['disk_path'] = disk_assignation[host][disk]['disk_path']

            containers_info.append(container_info)

    if len(containers_info) == 0:
        # Nothing to do
        return

    hosts = ','.join(list(added_containers.keys()))
    formatted_containers_info = str(containers_info).replace(' ','')

    # argument_list = [hosts, formatted_containers_info]
    # error_message = "Error starting containers {0}".format(formatted_containers_info)
    # process_script("start_containers", argument_list, error_message)
    run_playbooks.start_containers(list(added_containers.keys()), formatted_containers_info)


def deploy_app_containers(url, new_containers, app, app_files, container_resources, disk_assignation, app_type=None):

    added_containers = {}

    # Add containers to hosts in Ansible inventory
    with redis_server.lock(lock_key):
        for host in new_containers:
            added_containers[host] = {}
            for container_type in ['rm-nn','irregular','regular']:
                if container_type in new_containers[host]:
                    added_containers[host][container_type] = add_containers_to_hosts({host: new_containers[host][container_type]})[host]

    # Format containers info to use in Ansible playbooks
    containers_info = []
    for host in added_containers:
        for container_type in ['rm-nn', 'irregular', 'regular']:
            if container_type in added_containers[host]:
                for container in added_containers[host][container_type]:
                    container_info = {}
                    container_info['container_name'] = container
                    container_info['host'] = host
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
                    if config['disk_capabilities'] and config['disk_scaling'] and container_type != 'rm-nn':
                        for disk in disk_assignation[host]:
                            if disk_assignation[host][disk]['new_containers'] > 0:
                                disk_assignation[host][disk]['new_containers'] -= 1
                                container_info['disk'] = disk
                                container_info['disk_path'] = disk_assignation[host][disk]['disk_path']
                                for resource in ['disk_read', 'disk_write']:
                                    for key in ['max', 'min', 'weight', 'boundary', 'boundary_type']:
                                        resource_key = "{0}_{1}".format(resource,key)
                                        container_info[resource_key] = container_resources[container_type][resource_key]

                                break

                    containers_info.append(container_info)

    if len(containers_info) == 0:
        # Nothing to do
        return

    hosts = ','.join(list(added_containers.keys()))
    formatted_containers_info = str(containers_info).replace(' ', '')

    # Deploy containers through Ansible
    # argument_list = [hosts, formatted_containers_info, app_files['app_dir'], app_files['install_script'], app_files['app_jar'], app_type]
    # error_message = "Error starting containers {0}".format(formatted_containers_info)
    # process_script("start_containers_with_app", argument_list, error_message)
    run_playbooks.start_containers_with_app(list(added_containers.keys()), formatted_containers_info, app_type, app_files)

    return containers_info


## Start Apps
@shared_task(bind=True)
def start_app_task(self, url, app, app_files, new_containers, container_resources, disk_assignation, scaler_polling_freq, app_type=None):

    start_time = timeit.default_timer()

    # Set application in running state in ServerlessContainers
    change_app_execution_state_in_db(url, app, "run")

    # Deploy all the containers in the remote hosts
    app_containers = deploy_app_containers(url, new_containers, app, app_files, container_resources, disk_assignation, app_type)

    # Subscribe containers to app in ServerlessContainers
    subscribe_containers_to_app(url, app, app_containers)

    # Setup containers network to enable communications between containers
    setup_containers_network_task(url, app, app_containers, new_containers)

    # Start app inside all the containers
    start_app_on_containers(url, app, app_containers, app_files)

    # Wait for app to finish in all the containers
    wait_for_app_on_containers(app, app_containers)

    end_time = timeit.default_timer()
    runtime = "{:.2f}".format(end_time-start_time)
    update_task_runtime(self.request.id, runtime)

    # Destroy all the containers and remove them from ServerlessContainers
    remove_containers_from_app(url, app_containers, app, app_files, scaler_polling_freq)

@shared_task(bind=True)
def start_hadoop_app_task(self, url, app, app_files, new_containers, container_resources, disk_assignation, scaler_polling_freq, virtual_cluster, app_type="hadoop_app", global_hdfs_data=None):

    # Calculate resources for Hadoop cluster
    hadoop_resources = {}
    for container_type in ["regular", "irregular"]:
        # NOTE: 'irregular' container won't be created due to a previous workaround
        if container_type in container_resources:

            number_of_workers = 0
            for host in new_containers:
                if container_type in new_containers[host]: number_of_workers += new_containers[host][container_type]

            hadoop_resources[container_type] = set_hadoop_resources(container_resources[container_type], virtual_cluster, number_of_workers)

    start_time = timeit.default_timer()

    app_containers = deploy_app_containers(url, new_containers, app, app_files, container_resources, disk_assignation, app_type)
    rm_host, rm_container = setup_containers_hadoop_network_task(app_containers, url, app, app_files, hadoop_resources, new_containers, app_type, global_hdfs_data)

    end_time = timeit.default_timer()
    runtime = "{:.2f}".format(end_time-start_time)
    update_task_runtime(self.request.id, runtime)

    # Stop hadoop cluster
    run_playbooks.stop_hadoop_cluster(rm_host, rm_container)

    ## Disable scaler and other scaling services, remove all containers from StateDB and re-enable them
    run_playbooks.disable_scaler()
    run_playbooks.disable_scaling_services()

    start_time = timeit.default_timer()
    errors = []
    for container in app_containers:
        full_url = url + "container/{0}/{1}".format(container['container_name'],app)
        error = remove_container_from_app_db(full_url, container['container_name'], app)
        if error != "": errors.append(error)
    end_time = timeit.default_timer()

    ## Wait at least for the scaler polling frequency time before re-enabling it
    time.sleep(scaler_polling_freq - (end_time - start_time))

    run_playbooks.enable_scaler()
    run_playbooks.enable_scaling_services()

    ## Get timestamp to store output data
    timestamp = None
    if 'output_dir' in app_files and app_files['output_dir'] != '':
        timestamp = time.strftime("%Y-%m-%d--%H-%M-%S")

    ## Stop Containers
    # Remove master container first
    for container in app_containers:
        if container['container_name'] == rm_container:
            full_url = url + "container/{0}/{1}".format(rm_container,app)
            bind_path = ""
            if 'disk_path' in container: bind_path = container['disk_path']
            stop_app_on_container_task(rm_host, rm_container, bind_path, app, app_files, rm_container, timestamp)
            break

    # Stop and remove containers
    stop_containers_task = []
    for container in app_containers:
        if container['container_name'] != rm_container:
            full_url = url + "container/{0}/{1}".format(container['container_name'],app)
            bind_path = ""
            if 'disk_path' in container: bind_path = container['disk_path']
            stop_task = stop_app_on_container_task.delay(container['host'], container['container_name'], bind_path, app, app_files, rm_container, timestamp)
            register_task(stop_task.id,"stop_container_task")
            # stop_task = stop_app_on_container_task.si(container['host'], container['container_name'], bind_path, app, app_files, rm_container, timestamp)
            # stop_containers_task.append(stop_task)

    # set_hadoop_logs_timestamp_task = set_hadoop_logs_timestamp.si(app, app_files, rm_host, rm_container)
    # log_task = chord(stop_containers_task)(set_hadoop_logs_timestamp_task)
    # register_task(log_task.id,"stop_containers_task")

    if len(errors) > 0: raise Exception(str(errors))

# @shared_task
# def set_hadoop_logs_timestamp(app, app_files, rm_host, rm_container):

#     # argument_list = [app_files['app_jar'], rm_host, rm_container]
#     # error_message = "Error setting timestamp for hadoop logs for app {0}".format(app)
#     # process_script("set_hadoop_logs_timestamp", argument_list, error_message)
#     run_playbooks.set_hadoop_logs_timestamp(app_files['app_jar'], rm_host, rm_container)


@shared_task
def setup_containers_network_task(url, app, app_containers, new_containers):
    # Setup networks for a group of containers belonging to the same app
    # app_containers example = [{'container_name':'host1-cont0','host':'host1','cpu_max':200,'disk':'ssd_0',...},{'container_name':'host2-cont0','host':'host2',...}]
    hosts = ','.join(list(new_containers.keys()))
    formatted_app_containers = str(app_containers).replace(' ', '')

    run_playbooks.setup_network_on_containers(list(new_containers.keys()), formatted_app_containers)

@shared_task
def subscribe_containers_to_app(url, app, app_containers):
    run_playbooks.disable_scaler()
    run_playbooks.disable_scaling_services()

    # Subscribe containers to app in ServerlessContainers database
    for container in app_containers:
        full_url = url + "container/{0}/{1}".format(container['container_name'], app)
        add_container_to_app_in_db(full_url, container['container_name'], app)

    run_playbooks.enable_scaler()
    run_playbooks.enable_scaling_services()

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
        start_task = start_app_on_container_task.si(full_url, container['host'], container, app, app_files)
        tasks.append(start_task)

    result = group(tasks)()
    while not result.ready():
        time.sleep(1)
    result.get()


@shared_task
def setup_containers_hadoop_network_task(app_containers, url, app, app_files, hadoop_resources, new_containers, app_type="hadoop_app", global_hdfs_data=None):

    # Get rm-nn container (it is the first container from the host that got that container)
    for host in new_containers:
        if "rm-nn" in new_containers[host]:
            rm_host = host
            for container in app_containers:
                ## TODO: maybe differentiate rm_container using another parameter and not disk in case you dont want disk scaling on hadoop app
                if container['host'] == rm_host and 'disk' not in container:
                    rm_container = container
                    break
            break

    # app_containers example = [{'container_name':'host1-cont0','host':'host1','cpu_max':200,'disk':'ssd_0',...},{'container_name':'host2-cont0','host':'host2',...}]
    hosts = ','.join(list(new_containers.keys()))
    formatted_app_containers = str(app_containers).replace(' ','')

    # NOTE: 'irregular' container won't be created due to a previous workaround
    extracted_hadoop_resources = extract_hadoop_resources(hadoop_resources["regular"])

    argument_list = [hosts, app, app_type, formatted_app_containers, rm_host, rm_container['container_name']]
    argument_list.extend(extracted_hadoop_resources)

    if not global_hdfs_data:
        run_playbooks.setup_hadoop_network_on_containers(list(new_containers.keys()), app, app_type, formatted_app_containers, rm_host, rm_container['container_name'], hadoop_resources["regular"])
    else:
        ## Download required input data from global HDFS to local one
        run_playbooks.setup_hadoop_network_with_global_hdfs(list(new_containers.keys()), app, app_type, formatted_app_containers, rm_host, rm_container['container_name'], hadoop_resources["regular"], global_hdfs_data)

    # Subscribe containers to app in ServerlessContainers
    subscribe_containers_to_app(url, app, app_containers)

    # Lastly, start app on RM container
    full_url = url + "container/{0}/{1}".format(rm_container['container_name'],app)
    start_app_on_container_task(full_url, rm_host, rm_container, app, app_files)

    # Wait for RM container to finish
    wait_for_app_on_container_task(rm_host, rm_container, app)

    if global_hdfs_data:
        ## Upload generated output data from local HDFS to global one
        run_playbooks.upload_local_hdfs_data_to_global(rm_host, rm_container['container_name'], global_hdfs_data)

    return rm_host, rm_container['container_name']

@shared_task(bind=True)
def create_dir_on_hdfs(self, namenode_host, namenode_container, dir_to_create):

    # argument_list = [namenode_host, namenode_container, dir_to_create]
    # error_message = "Error creating directory {0} on HDFS".format(dir_to_create)
    # process_script("hdfs/create_dir_on_hdfs", argument_list, error_message)
    run_playbooks.create_dir_on_hdfs(namenode_host, namenode_container, dir_to_create)

@shared_task(bind=True)
def add_file_to_hdfs(self, namenode_host, namenode_container, file_to_add, dest_path):

    # argument_list = [namenode_host, namenode_container, file_to_add, dest_path]
    # error_message = "Error uploading {0} to {1} on HDFS".format(file_to_add, dest_path)
    # process_script("hdfs/add_file_to_hdfs", argument_list, error_message)
    if settings.PLATFORM_CONFIG["server_as_host"]:
        frontend_container = namenode_container
    else:
        frontend_container = settings.VARS_CONFIG["hdfs_frontend_container_name"]

    run_playbooks.add_file_to_hdfs(namenode_host, namenode_container, file_to_add, dest_path, frontend_container)

@shared_task(bind=True)
def get_file_from_hdfs(self, namenode_host, namenode_container, file_to_download, dest_path):

    # argument_list = [namenode_host, namenode_container, file_to_download, dest_path]
    # error_message = "Error downloading {0} from {1} on HDFS".format(file_to_download, dest_path)
    # process_script("hdfs/get_file_from_hdfs", argument_list, error_message)
    if settings.PLATFORM_CONFIG["server_as_host"]:
        frontend_container = namenode_container
    else:
        frontend_container = settings.VARS_CONFIG["hdfs_frontend_container_name"]

    run_playbooks.get_file_from_hdfs(namenode_host, namenode_container, file_to_download, dest_path, frontend_container)

@shared_task(bind=True)
def remove_file_from_hdfs(self, namenode_host, namenode_container, path_to_delete):

    # argument_list = [namenode_host, namenode_container, path_to_delete]
    # error_message = "Error removing path {0} from HDFS".format(path_to_delete)
    # process_script("hdfs/remove_file_from_hdfs", argument_list, error_message)
    run_playbooks.remove_file_from_hdfs(namenode_host, namenode_container, path_to_delete)

@shared_task(bind=True)
def start_global_hdfs_task(self, url, app, app_files, containers, virtual_cluster, put_field_data, hosts):

    # Calculate resources for HDFS cluster
    number_of_workers = len(containers) - 1

    worker_resources = None
    for container in containers:
        if "datanode" in container['container_name']:
            worker_resources = container
            break
    if not worker_resources: raise Exception("Worker container not found when starting global hdfs: {0}".format(containers))

    hdfs_resources = set_hadoop_resources(worker_resources, virtual_cluster, number_of_workers)

    start_time = timeit.default_timer()

    ## Create HDFS app
    add_app_task(url, put_field_data, app, app_files)

    ## Create and start containers
    # update inventory file
    with redis_server.lock(lock_key): add_containers_to_inventory(containers)

    nn_container = None
    nn_host = None
    for container in containers:
        if "namenode" in container['container_name']:
            nn_container = container['container_name']
            nn_host = container['host']
            if settings.PLATFORM_CONFIG["server_as_host"]:
                # Set additional variables to this specific container
                ## 'secondary_bind' --> bind directory that will be used to transfer data from local system to global HDFS
                ## 'expose_ptp' --> expose ptp as primary network connection to allow communication from server to namenode
                ## 'portmap' --> port mapping to allow direct communication from server to namenode
                container['secondary_bind'] = "{0}:{1}".format(settings.VARS_CONFIG['global_hdfs_data_dir'], settings.VARS_CONFIG['data_dir_on_container'])
                container['expose_ptp'] = 1
                container['portmap'] = "portmap={0}:{1}/tcp".format(settings.PLATFORM_CONFIG['local_namenode_port'], settings.PLATFORM_CONFIG['namenode_port'])
            break
    if not nn_container: raise Exception("Namenode container not found in container list") # should not happen

    host_list = []
    for host in hosts: host_list.append(host['name'])
    formatted_host_list = ",".join(host_list)
    formatted_containers_info = str(containers).replace(' ','')

    # Start containers
    # argument_list = [formatted_host_list, formatted_containers_info, app_files['app_dir'], app_files['install_script'], app_files['app_jar'], app_files['app_type']]
    # error_message = "Error starting containers {0}".format(formatted_containers_info)
    # process_script("start_containers_with_app", argument_list, error_message)
    run_playbooks.start_containers_with_app(host_list, formatted_containers_info, app_files['app_type'], app_files)

    ## Setup network and start HDFS
    # argument_list = [formatted_host_list, app, app_files['app_type'], formatted_containers_info, nn_host, nn_container, hdfs_resources["datanode_d_heapsize"]]
    # error_message = "Error setting HDFS network"
    # process_script("hdfs/setup_hdfs_network", argument_list, error_message)

    ## Run HDFS + YARN on the global HDFS cluster, thus distcp may be run within the global cluster
    run_playbooks.setup_hadoop_network_on_containers(host_list, app, app_files['app_type'], formatted_containers_info, nn_host, nn_container, hdfs_resources)


    # Add containers to app
    url = url[:url[:url.rfind('/')].rfind('/')]
    for container in containers:
        full_url = url + "/container/{0}/{1}".format(container['container_name'], app)
        add_container_to_app_in_db(full_url, container['container_name'], app)

    # Start hdfs frontend container
    # argument_list = [formatted_host_list, "hdfs_frontend", formatted_containers_info, nn_host, nn_container]
    # error_message = "Error setting HDFS frontend"
    # process_script("hdfs/start_hdfs_frontend", argument_list, error_message)
    if not settings.PLATFORM_CONFIG["server_as_host"]:
        run_playbooks.start_hdfs_frontend(host_list, "hdfs_frontend", formatted_containers_info, nn_host, nn_container)

    end_time = timeit.default_timer()
    runtime = "{:.2f}".format(end_time-start_time)
    update_task_runtime(self.request.id, runtime)

@shared_task(bind=True)
def stop_hdfs_task(self, url, app, app_files, app_containers, scaler_polling_freq, rm_host, rm_container):

    # Stop hadoop cluster
    run_playbooks.stop_hadoop_cluster(rm_host, rm_container)

    ## Disable scaler and other scaling services, remove all containers from StateDB and re-enable them
    run_playbooks.disable_scaler()
    run_playbooks.disable_scaling_services()

    start_time = timeit.default_timer()
    errors = []
    for container in app_containers:
        full_url = url + "container/{0}/{1}".format(container['name'],app)
        error = remove_container_from_app_db(full_url, container['name'], app)
        if error != "": errors.append(error)
    end_time = timeit.default_timer()

    ## Wait at least for the scaler polling frequency time before re-enabling it
    time.sleep(scaler_polling_freq - (end_time - start_time))

    run_playbooks.enable_scaler()
    run_playbooks.enable_scaling_services()

    # Remove app from db
    full_url = url + "apps" + "/" + app
    error_message = "Error removing app {0}".format(app)
    error, _ = request_to_state_db(full_url, "delete", error_message)

    ## Clean datanodes data_dir and avoid errors when creating new global_hdfs cluster
    ## This is a workaround, should be executed when stopping cluster
    for container in app_containers:
        # argument_list = [container['host'], container['name']]
        # error_message = "Error cleaning HDFS files from container {0}".format(container['name'])
        # process_script("hdfs/clean_hdfs", argument_list, error_message)
        run_playbooks.clean_hdfs(container['host'], container['name'])

    # Stop hdfs frontend container
    # argument_list = ["platform_server", vars_config['hdfs_frontend_container_name']]
    # error_message = "Error stopping hdfs frontend container {0}".format(vars_config['hdfs_frontend_container_name'])
    # process_script("stop_container", argument_list, error_message)
    if not settings.PLATFORM_CONFIG["server_as_host"]:
        run_playbooks.stop_container("platform_server", vars_config['hdfs_frontend_container_name'])

    # Stop containers
    stop_containers_task = []
    for container in app_containers:
        bind_path = ""
        #if 'disk_path' in container: bind_path = container['disk_path']
        if 'disk' in container['resources'] and 'path' in container['resources']['disk']: bind_path = container['resources']['disk']['path']
        stop_task = stop_container.delay(container['host'], container['name'], bind_path)
        register_task(stop_task.id,"stop_container_task")
        # stop_task = stop_container.si(container['host'], container['name'], bind_path)
        # stop_containers_task.append(stop_task)

    # Collect logs
    # set_hadoop_logs_timestamp_task = set_hadoop_logs_timestamp.si(app, app_files, rm_host, rm_container)
    # log_task = chord(stop_containers_task)(set_hadoop_logs_timestamp_task)
    # register_task(log_task.id,"stop_containers_task")


## Removes
@shared_task
def remove_host_task(full_url, host_name):

    error_message = "Error removing host {0}".format(host_name)
    error, _ = request_to_state_db(full_url, "delete", error_message)

    ## remove host
    if (not error):
            
        # stop node scaler service in host
        # argument_list = [host_name]
        # error_message = "Error stopping host {0} scaler service".format(host_name)
        # process_script("stop_host_scaler", argument_list, error_message)
        run_playbooks.stop_host_scaler(host_name)

        # update inventory file
        with redis_server.lock(lock_key):
            remove_host(host_name)
    else:
        raise Exception(error)

@shared_task
def remove_app_task(url, structure_type_url, app_name, container_list, app_files, user=None):

    # first, remove all containers from app
    if len(container_list) > 0:
        run_playbooks.disable_scaler()
        run_playbooks.disable_scaling_services()

        errors = []
        for container in container_list:
            full_url = url + "container/{0}/{1}".format(container['name'], app_name)
            error = remove_container_from_app_db(full_url, container['name'], app_name)
            if error != "": errors.append(error)

        run_playbooks.enable_scaler()
        run_playbooks.enable_scaling_services()

        ## Get timestamp to store output data
        timestamp = None
        if 'output_dir' in app_files and app_files['output_dir'] != '':
            timestamp = time.strftime("%Y-%m-%d--%H-%M-%S")

        for container in container_list:
            full_url = url + "container/{0}/{1}".format(container['name'], app_name)
            bind_path = container.get('disk_path', "")
            task = stop_app_on_container_task.delay(container['host'], container['name'], bind_path, app_name, app_files, "", timestamp)
            register_task(task.id, "stop_app_on_container_task")

    # If app is associated with a user, desubscribe app from user
    if user and user != "":
        full_url = settings.BASE_URL + "/user/clusters/" + user + "/" + app_name + "/"
        error_message = "Error removing app {0} from user {1}".format(app_name, user)
        error, _ = request_to_state_db(full_url, "delete", error_message)

        if error:
            raise Exception(error)

    # then, actually remove app
    full_url = url + structure_type_url + "/" + app_name

    error_message = "Error removing app {0}".format(app_name)
    error, _ = request_to_state_db(full_url, "delete", error_message)

@shared_task
def remove_containers_task(url, container_list):

    ## Disable scaler and other scaling services, remove all containers from StateDB and re-enable them
    run_playbooks.disable_scaler()
    run_playbooks.disable_scaling_services()

    errors = []
    for container in container_list:
        full_url = url + "container/{0}".format(container['container_name'])
        error = remove_container_from_db(full_url, container['container_name'])
        if error != "": errors.append(error)

    run_playbooks.enable_scaler()
    run_playbooks.enable_scaling_services()

    ## Stop Containers
    # Stop and remove containers
    for container in container_list:
        full_url = url + "container/{0}".format(container['container_name'])
        bind_path = ""
        if 'disk_path' in container: bind_path = container['disk_path']
        stop_task = stop_container.delay(container['host'], container['container_name'], bind_path)
        register_task(stop_task.id,"stop_container_task")

    # It would be great to execute tasks on a group, but the group task ID is not trackable

    if len(errors) > 0: raise Exception(str(errors))

@shared_task
def remove_containers_from_app(url, container_list, app, app_files, scaler_polling_freq):

    # Disable scaler and other scaling services before removing containers
    run_playbooks.disable_scaler()
    run_playbooks.disable_scaling_services()

    # Set application in stop state in ServerlessContainers
    change_app_execution_state_in_db(url, app, "stop")

    # Desubscribe containers from app in StateDB
    start_time = timeit.default_timer()
    errors = []
    for container in container_list:
        full_url = url + "container/{0}/{1}".format(container['container_name'],app)
        error = remove_container_from_app_db(full_url, container['container_name'], app)
        if error != "":
            errors.append(error)
    end_time = timeit.default_timer()

    ## Wait at least for the scaler polling frequency time before re-enabling it
    time.sleep(scaler_polling_freq - (end_time - start_time))

    # Re-enable Scaler
    run_playbooks.enable_scaler()
    run_playbooks.enable_scaling_services()

    ## Get timestamp to store output data
    timestamp = None
    if 'output_dir' in app_files and app_files['output_dir'] != '':
        timestamp = time.strftime("%Y-%m-%d--%H-%M-%S")

    ## Stop Containers
    # Stop and remove containers
    #stop_containers_task = []
    for container in container_list:
        full_url = url + "container/{0}/{1}".format(container['container_name'], app)
        bind_path = ""
        if 'disk_path' in container: bind_path = container['disk_path']
        stop_task = stop_app_on_container_task.delay(container['host'], container['container_name'], bind_path, app, app_files, "", timestamp)
        register_task(stop_task.id, "stop_container_task")
        #stop_task = stop_app_on_container_task.si(container['host'], container['container_name'], bind_path, app, app_files, "")
        #stop_containers_task.append(stop_task)

    # TODO: Maybe collect some kind of logs...
    # It would be great to execute tasks on a group, but the group task ID is not trackable
    #stop_group_task = group(stop_containers_task)()
    #register_task(stop_group_task.id,"stop_containers_task")

    if len(errors) > 0:
        raise Exception(str(errors))

@shared_task
def remove_users_task(url, users):
    run_playbooks.disable_scaler()
    run_playbooks.disable_scaling_services()

    errors = []
    for user_name in users:
        full_url = "{0}/{1}".format(url, user_name)
        error_message = "Error removing user {0}".format(user_name)
        error, _ = request_to_state_db(full_url, "delete", error_message)
        if error != "":
            errors.append(error)


    run_playbooks.enable_scaler()
    run_playbooks.enable_scaling_services()

    if len(errors) > 0:
        raise Exception(str(errors))

def remove_container_from_db(full_url, container_name):

    # Remove container from DB
    error_message = "Error removing container {0}".format(container_name)
    error, _ = request_to_state_db(full_url, "delete", error_message)

    return error

def remove_container_from_app_db(full_url, container_name, app):

    max_retries = 10
    actual_try = 0
    error = ""

    ## Ensure that container is deleted from app
    while actual_try < max_retries:

        # Remove container from app
        error_message = "Error removing container {0} from app {1}".format(container_name, app)
        error, response = request_to_state_db(full_url, "delete", error_message)

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
def stop_container(host, container_name, bind_path):

    ## Stop container
    # argument_list = [host, container_name]
    # error_message = "Error stopping container {0}".format(container_name)
    # process_script("stop_container", argument_list, error_message)
    run_playbooks.stop_container(host, container_name, bind_path)

    # update inventory file
    with redis_server.lock(lock_key):
        remove_container_from_host(container_name, host)

@shared_task
def stop_app_on_container_task(host, container_name, bind_path, app, app_files, rm_container, timestamp=None):
    run_playbooks.stop_app_on_container(host, container_name, app, app_files, rm_container, bind_path, timestamp)
    stop_container(host, container_name, bind_path)


### Deprecated functions
## Not used ATM
#@shared_task
def start_containers_task(host, new_containers, container_resources):

    # update inventory file
    with redis_server.lock(lock_key):
        added_containers = add_containers_to_hosts(new_containers)

    added_formatted_containers = container_list_to_formatted_str(added_containers[host])

    if added_formatted_containers == "":
        # Nothing to do
        return

    max_cpu_percentage_per_container = container_resources["cpu_max"]
    min_cpu_percentage_per_container = container_resources["cpu_min"]
    cpu_boundary = container_resources["cpu_boundary"]
    max_memory_per_container = container_resources["mem_max"]
    min_memory_per_container = container_resources["mem_min"]
    mem_boundary = container_resources["mem_boundary"]

    argument_list = [host, added_formatted_containers, max_cpu_percentage_per_container, min_cpu_percentage_per_container, cpu_boundary, max_memory_per_container, min_memory_per_container, mem_boundary]
    error_message = "Error starting containers {0}".format(added_formatted_containers)
    process_script("start_containers", argument_list, error_message)

## Not used ATM
#@shared_task
def start_containers_with_app_task(already_added_containers, url, host, new_containers, app, app_files, container_resources):
    #TODO: merge function with start_containers_task

    if new_containers == 0:
        # Nothing to do
        return already_added_containers

    # update inventory file
    with redis_server.lock(lock_key):
        added_containers = add_containers_to_hosts({host: new_containers})

    added_formatted_containers = container_list_to_formatted_str(added_containers[host])

    # Start containers
    if app_files['install_script'] and app_files['install_script'] != "":
        template_definition_file="app_container.def"
        definition_file = "{0}_container.def".format(app.replace(" ", "_"))
        image_file = "{0}_container.sif".format(app.replace(" ", "_"))
    elif app_files['app_jar'] and app_files['app_jar'] != "":
        template_definition_file="hadoop_container.def"
        definition_file = "hadoop_container.def"
        image_file = "hadoop_container.sif"
    else:
        template_definition_file="ubuntu_container.def"
        definition_file = "ubuntu_container.def"
        image_file = "ubuntu_container.sif"

    max_cpu_percentage_per_container = container_resources["cpu_max"]
    min_cpu_percentage_per_container = container_resources["cpu_min"]
    cpu_boundary = container_resources["cpu_boundary"]
    max_memory_per_container = container_resources["mem_max"]
    min_memory_per_container = container_resources["mem_min"]
    mem_boundary = container_resources["mem_boundary"]

    argument_list = [host, app, template_definition_file, definition_file, image_file, app_files['files_dir'], app_files['install_script'], app_files['app_jar'], 
        added_formatted_containers, max_cpu_percentage_per_container, min_cpu_percentage_per_container, cpu_boundary, max_memory_per_container, min_memory_per_container, mem_boundary]
    error_message = "Error starting containers {0}".format(added_formatted_containers)
    process_script("start_containers_with_app", argument_list, error_message)

    return mergeDictionary(already_added_containers,added_containers)

## Not used ATM
def start_app(url, app, app_files, new_containers, container_resources, disk_assignation):

    # TODO: setup network before starting app on containers -> first start containers (without starting app) then setup network and start app on the same task

    setup_network_task = setup_containers_network_task.s(url, app, app_files)
    start_containers_tasks = []

    # Start containers with app
    i = 0
    for host in new_containers:
        if "irregular" in new_containers[host]:
            # Start a chain of tasks so that containers of same host are started sequentially
            # tasks = chain(start_containers_with_app_task.si(url, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.si(url, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])).apply_async()
            # register_task(tasks.id,"start_containers_with_app_task")
            # start_containers_tasks.append(chain(start_containers_with_app_task.si({},url, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.s(url, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])))
            if i == 0:
                start_containers_tasks.append(chain(start_containers_with_app_task.s({},url, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.s(url, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])))
            else:
                start_containers_tasks.append(chain(start_containers_with_app_task.s(url, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.s(url, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])))

        else:
            # task = start_containers_with_app_task.delay(url, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])
            # register_task(task.id,"start_containers_with_app_task")
            # start_containers_tasks.append(start_containers_with_app_task.si({},url, host, new_containers[host]["regular"], app, app_files, container_resources["regular"]))
            if i == 0:
                start_containers_tasks.append(start_containers_with_app_task.s({},url, host, new_containers[host]["regular"], app, app_files, container_resources["regular"]))
            else:
                start_containers_tasks.append(start_containers_with_app_task.s(url, host, new_containers[host]["regular"], app, app_files, container_resources["regular"]))

        i += 1

    if len(start_containers_tasks) > 0:
        #task = chord(start_containers_tasks)(setup_network_task)

        start_containers_tasks.append(setup_network_task)
        task = chain(*start_containers_tasks).delay()
        register_task(task.id,"setup_containers_network_task")

## Not used ATM
def start_hadoop_app(url, app, app_files, new_containers, container_resources, disk_assignation):

    # Calculate resources for Hadoop cluster
    hadoop_resources = {}
    for container_type in ["regular","irregular"]:
        # NOTE: 'irregular' container won't be created due to a previous workaround
        if container_type in container_resources:
            hadoop_resources[container_type] = {}

            total_cores = max(int(container_resources[container_type]["cpu_max"])//100,1)
            min_cores = max(int(container_resources[container_type]["cpu_min"])//100,1)
            total_memory = int(container_resources[container_type]["mem_max"])
            total_disks = 1
            reserved_memory = get_node_reserved_memory(total_memory)
            available_memory = total_memory - reserved_memory
            min_container_size = get_min_container_size(total_memory)

            number_of_hadoop_containers = int(min(2*total_cores, 1.8*total_disks, available_memory/min_container_size))
            mem_per_container = max(min_container_size, available_memory/number_of_hadoop_containers)

            scheduler_maximum_memory = int(number_of_hadoop_containers * mem_per_container)
            scheduler_minimum_memory = int(mem_per_container)
            nodemanager_memory = scheduler_maximum_memory
            map_memory = scheduler_minimum_memory
            reduce_memory = int(min(2*mem_per_container, available_memory))
            mapreduce_am_memory = reduce_memory

            total_available_memory = 0
            for host in new_containers:
                if container_type in new_containers[host]:
                    total_available_memory += available_memory * new_containers[host][container_type]

            if total_available_memory < map_memory + reduce_memory + mapreduce_am_memory:
                memory_slice = nodemanager_memory/3.5
                scheduler_minimum_memory = int(memory_slice)
                map_memory = scheduler_minimum_memory
                reduce_memory = scheduler_minimum_memory
                mapreduce_am_memory = int(1.5 * memory_slice)

            map_memory_java_opts = int(0.8 * map_memory)
            reduce_memory_java_opts = int(0.8 * reduce_memory)
            mapreduce_am_memory_java_opts = int(0.8* mapreduce_am_memory)

            hadoop_resources[container_type]["vcores"] = str(total_cores)
            hadoop_resources[container_type]["min_vcores"] = str(min_cores)
            hadoop_resources[container_type]["scheduler_maximum_memory"] = str(scheduler_maximum_memory)
            hadoop_resources[container_type]["scheduler_minimum_memory"] = str(scheduler_minimum_memory)
            hadoop_resources[container_type]["nodemanager_memory"] = str(nodemanager_memory)
            hadoop_resources[container_type]["map_memory"] = str(map_memory)
            hadoop_resources[container_type]["map_memory_java_opts"] = str(map_memory_java_opts)
            hadoop_resources[container_type]["reduce_memory"] = str(reduce_memory)
            hadoop_resources[container_type]["reduce_memory_java_opts"] = str(reduce_memory_java_opts)
            hadoop_resources[container_type]["mapreduce_am_memory"] = str(mapreduce_am_memory)
            hadoop_resources[container_type]["mapreduce_am_memory_java_opts"] = str(mapreduce_am_memory_java_opts)

    start_time = timeit.default_timer()
    setup_network_task = setup_containers_hadoop_network_task.s(url, app, app_files, hadoop_resources, new_containers, start_time)
    start_containers_tasks = []

    # Start containers with app
    i = 0
    for host in new_containers:
        start_host_containers_taks = []

        for container_type in ["rm-nn", "irregular", "regular"]:
            # NOTE: 'irregular' container won't be created due to a previous workaround
            if container_type in new_containers[host]:
                if i == 0:
                    start_host_containers_taks.append(start_containers_with_app_task.s({}, url, host, new_containers[host][container_type], app, app_files, container_resources[container_type]))
                else:
                    start_host_containers_taks.append(start_containers_with_app_task.s(url, host, new_containers[host][container_type], app, app_files, container_resources[container_type]))
                i += 1

        start_containers_tasks.append(chain(*start_host_containers_taks))

    if len(start_containers_tasks) > 0:
        start_containers_tasks.append(setup_network_task)
        task = chain(*start_containers_tasks).delay()
        register_task(task.id,"{0}_app_task".format(app))

## Not used ATM
#@shared_task
def remove_container_task(full_url, host_name, cont_name):

    error_message = "Error removing container {0}".format(cont_name)
    error, _ = request_to_state_db(full_url, "delete", error_message)

    ## stop container
    if error == "":
        argument_list = [host_name, cont_name]
        error_message = "Error stopping container {0}".format(cont_name)
        process_script("stop_container", argument_list, error_message)

        # update inventory file
        with redis_server.lock(lock_key):
            remove_container_from_host(cont_name,host_name)
    else:
        raise Exception(error)

## Not used ATM
#@shared_task
def remove_container_from_app_task(full_url, host, container_name, bind_path, app, app_files, rm_container):

    files_dir = app_files['files_dir']
    install_script = app_files['install_script']
    start_script = app_files['start_script']
    stop_script = app_files['stop_script']
    app_jar = app_files['app_jar']

    argument_list = [host, container_name, app, files_dir, install_script, start_script, stop_script, app_jar, bind_path, rm_container]
    error_message = "Error stopping app {0} on container {1}".format(app, container_name)
    process_script("stop_app_on_container", argument_list, error_message)

    # full_url[:full_url.rfind('/')] removes the last part of url -> .../container/host0-cont0/app1 -> .../container/host0-cont0
    remove_container_task(full_url[:full_url.rfind('/')], host, container_name)