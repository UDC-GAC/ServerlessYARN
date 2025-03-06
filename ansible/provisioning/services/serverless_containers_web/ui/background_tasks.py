import time
import subprocess
from ui.update_inventory_file import add_containers_to_hosts,remove_container_from_host, add_host, remove_host, add_disks_to_hosts
from ui.utils import request_to_state_db
from celery import shared_task, chain, chord, group
from celery.result import AsyncResult, allow_join_result
import redis
import json
import timeit
import yaml

config_path = "../../config/config.yml"
with open(config_path, "r") as config_file:
    config = yaml.load(config_file, Loader=yaml.FullLoader)

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

def get_pendings_tasks_to_string():
    still_pending_tasks, successful_tasks, failed_tasks = get_pending_tasks()

    still_pending_tasks_string = []
    successful_tasks_string = []
    failed_tasks_string = []

    for task_id, task_name in still_pending_tasks:
        info = "Task with ID {0} and name {1} is pending".format(task_id,task_name)
        still_pending_tasks_string.append(info)

    for task_id, task_name, runtime in successful_tasks:
        if runtime != None: runtime_str = " in {0} seconds".format(runtime)
        else: runtime_str = ""
        success = "Task with ID {0} and name {1} has completed successfully{2}".format(task_id,task_name,runtime_str)
        successful_tasks_string.append(success)

    for task_id, task_name, task_error in failed_tasks:
        error = "Task with ID {0} and name {1} has failed with error: {2}".format(task_id,task_name,task_error)
        failed_tasks_string.append(error)

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

    argument_list = [host]
    error_message = "Error adding host {0}".format(host)
    process_script("configure_host", argument_list, error_message)

@shared_task
def add_disks_to_hosts_task(host_list, add_to_lv, new_disks, extra_disk):

    # update_inventory_file
    with redis_server.lock(lock_key):
        added_disks = add_disks_to_hosts(host_list,new_disks)

    if add_to_lv:
        ## Add disks to existing LV
        argument_list = [','.join(host_list), " ".join(new_disks), extra_disk]
        error_message = "Error extending LV of hosts {0} with disks {1} and extra disk {2}".format(host_list, str(new_disks), extra_disk)
        process_script("extend_lv", argument_list, error_message)

    else:
        ## Add disks just as new individual disks
        formatted_added_disks = str(added_disks).replace(' ','')
        argument_list = [','.join(host_list), formatted_added_disks]
        error_message = "Error adding disks {0} to hosts {1}".format(str(new_disks), host_list)
        process_script("add_disks", argument_list, error_message)

@shared_task
def add_app_task(full_url, put_field_data, app, app_files):

    error_message = "Error adding app {0}".format(app)
    error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)

    if (not error):

        ## TODO: discuss which of the following versions should be used
        ## V1: send install_script, files_dir, etc into create_app script as args
        #if (app_files['install_script'] != ""):

        app_dir = app_files['app_dir']
        files_dir = app_files['files_dir']
        install_script = app_files['install_script']
        app_type = app_files['app_type']
        app_jar = app_files['app_jar']

        argument_list = [app_dir, files_dir, install_script, app_type, app_jar]
        error_message = "Error creating app {0}".format(app)
        process_script("create_app", argument_list, error_message)

        # ## V2: just send app name as argument for the script
        # argument_list = [app]
        # error_message = "Error creating app {0}".format(app)
        # process_script("create_app", argument_list, error_message)

    else:
        raise Exception(error)

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

@shared_task
def add_container_to_app_task(full_url, host, container, app, app_files):

    app_dir = app_files['app_dir']
    files_dir = app_files['files_dir']
    install_script = app_files['install_script']
    start_script = app_files['start_script']
    stop_script = app_files['stop_script']
    app_jar = app_files['app_jar']

    bind_path = ""
    if 'disk_path' in container:
        bind_path = container['disk_path']

    argument_list = [host, container['container_name'], app, app_dir, files_dir, install_script, start_script, stop_script, app_jar, bind_path]
    error_message = "Error starting app {0} on container {1}".format(app, container['container_name'])
    process_script("start_app_on_container", argument_list, error_message)

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
            for resource in ['cpu', 'mem', 'disk', 'energy']:
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

    argument_list = [hosts, formatted_containers_info]
    error_message = "Error starting containers {0}".format(formatted_containers_info)
    process_script("start_containers", argument_list, error_message)

def start_containers_with_app_task_v2(url, new_containers, app, app_files, container_resources, disk_assignation, app_type=None):

    added_containers = {}

    # update inventory file
    with redis_server.lock(lock_key):
        for host in new_containers:
            added_containers[host] = {}
            for container_type in ['rm-nn','irregular','regular']:
                if container_type in new_containers[host]:
                    added_containers[host][container_type] = add_containers_to_hosts({host: new_containers[host][container_type]})[host]

    containers_info = []

    for host in added_containers:
        for container_type in ['rm-nn','irregular','regular']:
            if container_type in added_containers[host]:
                for container in added_containers[host][container_type]:
                    container_info = {}
                    container_info['container_name'] = container
                    container_info['host'] = host
                    # Resources
                    for resource in ['cpu', 'mem']:
                        for key in ['max', 'min', 'weight', 'boundary', 'boundary_type']:
                            resource_key = "{0}_{1}".format(resource,key)
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
                                for resource in ['disk_max', 'disk_min', 'disk_weight', 'disk_boundary', 'disk_boundary_type']:
                                    container_info[resource] = container_resources[container_type][resource]
                                break

                    containers_info.append(container_info)

    if len(containers_info) == 0:
        # Nothing to do
        return

    hosts = ','.join(list(added_containers.keys()))
    formatted_containers_info = str(containers_info).replace(' ','')

    # Start containers
    argument_list = [hosts, formatted_containers_info, app_files['app_dir'], app_files['install_script'], app_files['app_jar'], app_type]
    error_message = "Error starting containers {0}".format(formatted_containers_info)
    process_script("start_containers_with_app", argument_list, error_message)

    return containers_info


## Start Apps
@shared_task(bind=True)
def start_app_task(self, url, app, app_files, new_containers, container_resources, disk_assignation, scaler_polling_freq, app_type=None):

    start_time = timeit.default_timer()

    app_containers = start_containers_with_app_task_v2(url, new_containers, app, app_files, container_resources, disk_assignation, app_type)
    setup_containers_network_task(app_containers, url, app, app_files, new_containers)

    end_time = timeit.default_timer()
    runtime = "{:.2f}".format(end_time-start_time)
    update_task_runtime(self.request.id, runtime)

    remove_containers_from_app(url, app_containers, app, app_files, scaler_polling_freq)

@shared_task(bind=True)
def start_hadoop_app_task(self, url, app, app_files, new_containers, container_resources, disk_assignation, scaler_polling_freq, virtual_cluster, app_type="hadoop_app"):

    # Calculate resources for Hadoop cluster
    hadoop_resources = {}
    for container_type in ["regular", "irregular"]:
        # NOTE: 'irregular' container won't be created due to a previous workaround
        if container_type in container_resources:
            hadoop_resources[container_type] = {}

            total_cores = max(int(container_resources[container_type]["cpu_max"])//100,1)
            min_cores = max(int(container_resources[container_type]["cpu_min"])//100,1)
            total_memory = int(container_resources[container_type]["mem_max"])
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
                datanode_d_heapsize = 128
                nodemanager_d_heapsize = 128
            else:
                ## Physical cluster config (real environment with (presumably) high resources)
                hyperthreading = True
                app_master_heapsize = 1024
                datanode_d_heapsize = 1024
                nodemanager_d_heapsize = 1024

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
            nodemanager_memory = available_memory - nodemanager_d_heapsize - datanode_d_heapsize

            mem_per_container = int((nodemanager_memory - mapreduce_am_memory) / total_cores)

            map_memory_ratio = 1
            reduce_memory_ratio = 1
            map_memory = int(min(mem_per_container * map_memory_ratio, available_memory))
            reduce_memory = int(min(mem_per_container * reduce_memory_ratio, available_memory))

            scheduler_maximum_memory = nodemanager_memory
            #scheduler_minimum_memory = int(mem_per_container)
            scheduler_minimum_memory = 256

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

            map_memory_java_opts = int(heapsize_factor * map_memory)
            reduce_memory_java_opts = int(heapsize_factor * reduce_memory)
            #mapreduce_am_memory_java_opts = int(heapsize_factor * mapreduce_am_memory)
            mapreduce_am_memory_java_opts = app_master_heapsize

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
            hadoop_resources[container_type]["datanode_d_heapsize"] = str(datanode_d_heapsize)
            hadoop_resources[container_type]["nodemanager_d_heapsize"] = str(nodemanager_d_heapsize)

            # Check assigned resources are valid
            for resource in hadoop_resources[container_type]:
                value = int(hadoop_resources[container_type][resource])
                if value <= 0:
                    bottleneck_resource = "CPU" if resource in ["vcores", "min_vcores"] else "memory"
                    raise Exception("Error allocating resources for containers in Hadoop application. "
                                    "Value for '{0}' is negative ({1}). The application may have been assigned "
                                    "too low {2} values.".format(resource, value, bottleneck_resource))

    start_time = timeit.default_timer()

    app_containers = start_containers_with_app_task_v2(url, new_containers, app, app_files, container_resources, disk_assignation, app_type)
    rm_host, rm_container = setup_containers_hadoop_network_task(app_containers, url, app, app_files, hadoop_resources, new_containers, app_type)

    end_time = timeit.default_timer()
    runtime = "{:.2f}".format(end_time-start_time)
    update_task_runtime(self.request.id, runtime)

    # Stop hadoop cluster
    argument_list = [rm_host, rm_container]
    error_message = "Error stopping hadoop cluster for app {0}".format(app)
    process_script("stop_hadoop_cluster", argument_list, error_message)

    ## Disable scaler, remove all containers from StateDB and re-enable scaler
    argument_list = []
    error_message = "Error disabling scaler"
    process_script("disable_scaler", argument_list, error_message)

    start_time = timeit.default_timer()
    errors = []
    for container in app_containers:
        full_url = url + "container/{0}/{1}".format(container['container_name'],app)
        error = remove_container_from_app_db(full_url, container['container_name'], app)
        if error != "": errors.append(error)
    end_time = timeit.default_timer()

    ## Wait at least for the scaler polling frequency time before re-enabling it
    time.sleep(scaler_polling_freq - (end_time - start_time))

    argument_list = []
    error_message = "Error re-enabling scaler"
    process_script("enable_scaler", argument_list, error_message)

    ## Stop Containers
    # Remove master container first
    for container in app_containers:
        if container['container_name'] == rm_container:
            full_url = url + "container/{0}/{1}".format(rm_container,app)
            bind_path = ""
            if 'disk_path' in container: bind_path = container['disk_path']
            stop_app_on_container_task(rm_host, rm_container, bind_path, app, app_files, rm_container)
            break

    # Stop and remove containers
    stop_containers_task = []
    for container in app_containers:
        if container['container_name'] != rm_container:
            full_url = url + "container/{0}/{1}".format(container['container_name'],app)
            bind_path = ""
            if 'disk_path' in container: bind_path = container['disk_path']
            stop_task = stop_app_on_container_task.si(container['host'], container['container_name'], bind_path, app, app_files, rm_container)
            stop_containers_task.append(stop_task)

    set_hadoop_logs_timestamp_task = set_hadoop_logs_timestamp.si(app, app_files, rm_host, rm_container)
    log_task = chord(stop_containers_task)(set_hadoop_logs_timestamp_task)
    register_task(log_task.id,"stop_containers_task")

    if len(errors) > 0: raise Exception(str(errors))

@shared_task
def set_hadoop_logs_timestamp(app, app_files, rm_host, rm_container):

    argument_list = [app_files['app_jar'], rm_host, rm_container]
    error_message = "Error setting timestamp for hadoop logs for app {0}".format(app)
    process_script("set_hadoop_logs_timestamp", argument_list, error_message)

## Setup network for apps
@shared_task
def setup_containers_network_task(app_containers, url, app, app_files, new_containers):

    # app_containers example = [{'container_name':'host1-cont0','host':'host1','cpu_max':200,'disk':'ssd_0',...},{'container_name':'host2-cont0','host':'host2',...}]
    hosts = ','.join(list(new_containers.keys()))
    formatted_app_containers = str(app_containers).replace(' ','')

    argument_list = [hosts, formatted_app_containers]
    error_message = "Error setting network for app {0}".format(app)
    process_script("setup_network_on_containers", argument_list, error_message)

    # Add containers to app
    for container in app_containers:
        full_url = url + "container/{0}/{1}".format(container['container_name'], app)
        add_container_to_app_in_db(full_url, container['container_name'], app)

    # Start app on containers
    start_containers_task = []
    for container in app_containers:
        full_url = url + "container/{0}/{1}".format(container['container_name'],app)
        start_task = add_container_to_app_task.si(full_url, container['host'], container, app, app_files)
        start_containers_task.append(start_task)

    start_group_task = group(start_containers_task)

    task = start_group_task()
    while not task.ready():
        time.sleep(1)
    task.get()


@shared_task
def setup_containers_hadoop_network_task(app_containers, url, app, app_files, hadoop_resources, new_containers, app_type="hadoop_app"):

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
    vcores = hadoop_resources["regular"]["vcores"]
    min_vcores = hadoop_resources["regular"]["min_vcores"]
    scheduler_maximum_memory = hadoop_resources["regular"]["scheduler_maximum_memory"]
    scheduler_minimum_memory = hadoop_resources["regular"]["scheduler_minimum_memory"]
    nodemanager_memory = hadoop_resources["regular"]["nodemanager_memory"]
    map_memory = hadoop_resources["regular"]["map_memory"]
    map_memory_java_opts = hadoop_resources["regular"]["map_memory_java_opts"]
    reduce_memory = hadoop_resources["regular"]["reduce_memory"]
    reduce_memory_java_opts = hadoop_resources["regular"]["reduce_memory_java_opts"]
    mapreduce_am_memory = hadoop_resources["regular"]["mapreduce_am_memory"]
    mapreduce_am_memory_java_opts = hadoop_resources["regular"]["mapreduce_am_memory_java_opts"]
    datanode_d_heapsize = hadoop_resources["regular"]["datanode_d_heapsize"]
    nodemanager_d_heapsize =  hadoop_resources["regular"]["nodemanager_d_heapsize"]

    argument_list = [hosts, app, app_type, formatted_app_containers, rm_host, rm_container['container_name'],
        vcores, min_vcores, scheduler_maximum_memory, scheduler_minimum_memory, nodemanager_memory,
        map_memory, map_memory_java_opts, reduce_memory, reduce_memory_java_opts, mapreduce_am_memory,
        mapreduce_am_memory_java_opts, datanode_d_heapsize, nodemanager_d_heapsize]

    error_message = "Error setting network for app {0}".format(app)
    process_script("setup_hadoop_network_on_containers", argument_list, error_message)

    # Add containers to app
    for container in app_containers:
        full_url = url + "container/{0}/{1}".format(container['container_name'], app)
        add_container_to_app_in_db(full_url, container['container_name'], app)

    # Lastly, start app on RM container
    full_url = url + "container/{0}/{1}".format(rm_container['container_name'],app)
    add_container_to_app_task(full_url, rm_host, rm_container, app, app_files)

    return rm_host, rm_container['container_name']

## Removes
@shared_task
def remove_host_task(full_url, host_name):

    error_message = "Error removing host {0}".format(host_name)
    error, _ = request_to_state_db(full_url, "delete", error_message)

    ## remove host
    if (not error):
            
        # stop node scaler service in host
        argument_list = [host_name]
        error_message = "Error stopping host {0} scaler service".format(host_name)
        process_script("stop_host_scaler", argument_list, error_message)

        # update inventory file
        with redis_server.lock(lock_key):
            remove_host(host_name)
    else:
        raise Exception(error)

@shared_task
def remove_app_task(url, structure_type_url, app_name, container_list, app_files):

    # first, remove all containers from app
    if len(container_list) > 0:
        argument_list = []
        error_message = "Error disabling scaler"
        process_script("disable_scaler", argument_list, error_message)

        errors = []
        for container in container_list:
            full_url = url + "container/{0}/{1}".format(container['name'], app_name)
            error = remove_container_from_app_db(full_url, container['name'], app_name)
            if error != "": errors.append(error)

        argument_list = []
        error_message = "Error re-enabling scaler"
        process_script("enable_scaler", argument_list, error_message)

        for container in container_list:
            full_url = url + "container/{0}/{1}".format(container['name'], app_name)
            bind_path = ""
            if 'disk_path' in container: bind_path = container['disk_path']
            task = stop_app_on_container_task.delay(container['host'], container['name'], bind_path, app_name, app_files, "")
            register_task(task.id, "stop_app_on_container_task")

    # then, actually remove app
    full_url = url + structure_type_url + "/" + app_name

    error_message = "Error removing app {0}".format(app_name)
    error, _ = request_to_state_db(full_url, "delete", error_message)

    if (error): raise Exception(error)

@shared_task
def remove_containers(url, container_list):

    ## Disable scaler, remove all containers from StateDB and re-enable scaler
    argument_list = []
    error_message = "Error disabling scaler"
    process_script("disable_scaler", argument_list, error_message)

    errors = []
    for container in container_list:
        full_url = url + "container/{0}".format(container['container_name'])
        error = remove_container_from_db(full_url, container['container_name'])
        if error != "": errors.append(error)

    argument_list = []
    error_message = "Error re-enabling scaler"
    process_script("enable_scaler", argument_list, error_message)

    ## Stop Containers
    # Stop and remove containers
    for container in container_list:
        full_url = url + "container/{0}".format(container['container_name'])
        stop_task = stop_container.delay(container['host'], container['container_name'])
        register_task(stop_task.id,"stop_container_task")

    # It would be great to execute tasks on a group, but the group task ID is not trackable

    if len(errors) > 0: raise Exception(str(errors))

@shared_task
def remove_containers_from_app(url, container_list, app, app_files, scaler_polling_freq):

    ## Disable scaler, remove all containers from StateDB and re-enable scaler
    argument_list = []
    error_message = "Error disabling scaler"
    process_script("disable_scaler", argument_list, error_message)

    start_time = timeit.default_timer()
    errors = []
    for container in container_list:
        full_url = url + "container/{0}/{1}".format(container['container_name'],app)
        error = remove_container_from_app_db(full_url, container['container_name'], app)
        if error != "": errors.append(error)
    end_time = timeit.default_timer()

    ## Wait at least for the scaler polling frequency time before re-enabling it
    time.sleep(scaler_polling_freq - (end_time - start_time))

    argument_list = []
    error_message = "Error re-enabling scaler"
    process_script("enable_scaler", argument_list, error_message)

    ## Stop Containers
    # Stop and remove containers
    #stop_containers_task = []
    for container in container_list:
        full_url = url + "container/{0}/{1}".format(container['container_name'],app)
        bind_path = ""
        if 'disk_path' in container: bind_path = container['disk_path']
        stop_task = stop_app_on_container_task.delay(container['host'], container['container_name'], bind_path, app, app_files, "")
        register_task(stop_task.id,"stop_container_task")
        #stop_task = stop_app_on_container_task.si(container['host'], container['container_name'], bind_path, app, app_files, "")
        #stop_containers_task.append(stop_task)

    # TODO: Maybe collect some kind of logs...
    # It would be great to execute tasks on a group, but the group task ID is not trackable
    #stop_group_task = group(stop_containers_task)()
    #register_task(stop_group_task.id,"stop_containers_task")

    if len(errors) > 0: raise Exception(str(errors))

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
def stop_container(host, container_name):

    ## Stop container
    argument_list = [host, container_name]
    error_message = "Error stopping container {0}".format(container_name)
    process_script("stop_container", argument_list, error_message)

    # update inventory file
    with redis_server.lock(lock_key):
        remove_container_from_host(container_name, host)

@shared_task
def stop_app_on_container_task(host, container_name, bind_path, app, app_files, rm_container):

    ## Stop app on container
    app_dir = app_files['app_dir']
    files_dir = app_files['files_dir']
    install_script = app_files['install_script']
    start_script = app_files['start_script']
    stop_script = app_files['stop_script']
    app_jar = app_files['app_jar']

    argument_list = [host, container_name, app, app_dir, files_dir, install_script, start_script, stop_script, app_jar, bind_path, rm_container]
    error_message = "Error stopping app {0} on container {1}".format(app, container_name)
    process_script("stop_app_on_container", argument_list, error_message)

    stop_container(host, container_name)


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
    if (error == ""):

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