import time
import subprocess
import requests
from ui.update_inventory_file import add_containers_to_hosts,remove_container_from_host, add_host, remove_host
from celery import shared_task, chain, chord
from celery.result import AsyncResult
from bs4 import BeautifulSoup
import redis
import json

r = redis.Redis()
redis_prefix = "pending_tasks"
# TODO: check if lock is actually working
lock = r.lock("celery")

def register_task(task_id, task_name):
    key = "{0}:{1}".format(redis_prefix,task_id)
    r.mset({key: task_name})

def get_pending_tasks():
    still_pending_tasks = []
    successful_tasks = []
    failed_tasks = []

    for key in r.scan_iter("{0}:*".format(redis_prefix)):
        task_name = r.get(key).decode("utf-8")
        task_id = key.decode("utf-8")[len(redis_prefix) + 1:]
        task_result = AsyncResult(task_id)
        status = task_result.status

        if status != "SUCCESS" and status != "FAILURE":
            still_pending_tasks.append((task_id,task_name))
        elif status == "SUCCESS":
            successful_tasks.append((task_id,task_name))
        else:
            failed_tasks.append((task_id,task_name,task_result.result))

    # remove completed or failed tasks
    for task_id, task_name in successful_tasks:
        r.delete("{0}:{1}".format(redis_prefix, task_id))

    for task_id, task_name, task_error in failed_tasks:
        r.delete("{0}:{1}".format(redis_prefix, task_id))

    # TODO: remove pending tasks after a timeout

    return still_pending_tasks, successful_tasks, failed_tasks

def get_pendings_tasks_to_string():
    still_pending_tasks, successful_tasks, failed_tasks = get_pending_tasks()

    still_pending_tasks_string = []
    successful_tasks_string = []
    failed_tasks_string = []

    for task_id, task_name in still_pending_tasks:
        info = "Task with ID {0} and name {1} is pending".format(task_id,task_name)
        still_pending_tasks_string.append(info)

    for task_id, task_name in successful_tasks:
        success = "Task with ID {0} and name {1} has completed successfully".format(task_id,task_name)
        successful_tasks_string.append(success)

    for task_id, task_name, task_error in failed_tasks:
        error = "Task with ID {0} and name {1} has failed with error: {2}".format(task_id,task_name,task_error)
        failed_tasks_string.append(error)

    return still_pending_tasks_string, successful_tasks_string, failed_tasks_string


def container_list_to_formatted_str(container_list):
    return str(container_list).replace('[','').replace(']','').replace(', ',',').replace('\'','')

@shared_task
def start_containers_task(host, new_containers, container_resources):

    # update inventory file
    with lock:
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

    rc = subprocess.Popen([
        "./ui/scripts/start_containers.sh",host,added_formatted_containers, max_cpu_percentage_per_container, min_cpu_percentage_per_container, cpu_boundary, max_memory_per_container, min_memory_per_container, mem_boundary
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = rc.communicate()

    # Log ansible output
    print(out.decode("utf-8") )

    if rc.returncode != 0:
        error = "Error starting containers {0}: {1}".format(added_formatted_containers,err.decode("utf-8"))
        raise Exception(error)

@shared_task
def add_host_task(host,cpu,mem,new_containers):

    # update_inventory_file
    with lock:
        add_host(structure_name,cpu,mem,new_containers)

    rc = subprocess.Popen(["./ui/scripts/configure_host.sh",host], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = rc.communicate()

    # Log ansible output
    print(out.decode("utf-8") )

    if rc.returncode != 0:
        error = "Error adding host {0}: {1}".format(host, err.decode("utf-8"))
        raise Exception(error)

@shared_task
def add_app_task(full_url, headers, put_field_data, app, app_files):

    r = requests.put(full_url, data=json.dumps(put_field_data), headers=headers)

    error = ""
    if (r != "" and r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error adding app " + app + ": " + soup.get_text().strip()

    if (error == ""):

        if (app_files['install_script'] != ""):

            definition_file = "{0}_container.def".format(app.replace(" ", "_"))
            image_file = "{0}_container.sif".format(app.replace(" ", "_"))
            files_dir = app_files['files_dir']
            install_script = app_files['install_script']

            rc = subprocess.Popen(["./ui/scripts/create_app.sh",definition_file, image_file, app, files_dir, install_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = rc.communicate()

            # Log ansible output
            print(out.decode("utf-8") )

            if rc.returncode != 0:
                error = "Error creating app {0}: {1}".format(app, err.decode("utf-8"))
                raise Exception(error)

    else:
        raise Exception(error)

def start_app(url, headers, app, app_files, new_containers, container_resources):

    # TODO: setup network before starting app on containers -> first start containers (without starting app) then setup network and start app on the same task

    setup_network_task = setup_containers_network_task.s(url, headers, app, app_files)
    start_containers_tasks = []

    # Start containers with app
    i = 0
    for host in new_containers:
        if "irregular" in new_containers[host]:
            # Start a chain of tasks so that containers of same host are started sequentially
            # tasks = chain(start_containers_with_app_task.si(url, headers, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.si(url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])).apply_async()
            # register_task(tasks.id,"start_containers_with_app_task")
            # start_containers_tasks.append(chain(start_containers_with_app_task.si({},url, headers, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.s(url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])))
            if i == 0:
                start_containers_tasks.append(chain(start_containers_with_app_task.s({},url, headers, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.s(url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])))
            else:
                start_containers_tasks.append(chain(start_containers_with_app_task.s(url, headers, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.s(url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])))

        else:
            # task = start_containers_with_app_task.delay(url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])
            # register_task(task.id,"start_containers_with_app_task")
            # start_containers_tasks.append(start_containers_with_app_task.si({},url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"]))
            if i == 0:
                start_containers_tasks.append(start_containers_with_app_task.s({},url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"]))
            else:
                start_containers_tasks.append(start_containers_with_app_task.s(url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"]))

        i += 1

    if len(start_containers_tasks) > 0:
        # Celery chords may be the best solution, but they seem to be somewhat bugged
        #task = chord(start_containers_tasks)(setup_network_task)

        start_containers_tasks.append(setup_network_task)
        task = chain(*start_containers_tasks).delay()
        register_task(task.id,"setup_containers_network_task")

def start_hadoop_app(url, headers, app, app_files, new_containers, container_resources):

    # TODO: setup network before starting app on containers -> first start containers (without starting app) then setup network and start app on the same task

    # Calculate resources for Hadoop cluster
    hadoop_resources = {}
    # TODO: avoid underusing resources (example: an irregular container with low resources limiting the whole hadoop cluster)
    for resource_type in ["regular","irregular"]:
        if resource_type in container_resources:
            hadoop_resources[resource_type] = {}

            total_cores = int(container_resources[resource_type]["cpu_max"])//100
            total_memory = int(container_resources[resource_type]["mem_max"])
            total_disks = 1
            reserved_memory = 512 # take value from table
            available_memory = total_memory - reserved_memory
            min_container_size = 512 # take value from table

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
                if resource_type in new_containers[host]:
                    total_available_memory += available_memory * new_containers[host][resource_type]

            if total_available_memory < map_memory + reduce_memory + mapreduce_am_memory:
                memory_slice = nodemanager_memory/3.5
                scheduler_minimum_memory = int(memory_slice)
                map_memory = scheduler_minimum_memory
                reduce_memory = scheduler_minimum_memory
                mapreduce_am_memory = int(1.5 * memory_slice)

            map_memory_java_opts = int(0.8 * map_memory)
            reduce_memory_java_opts = int(0.8 * reduce_memory)
            mapreduce_am_memory_java_opts = int(0.8* mapreduce_am_memory)

            hadoop_resources[resource_type]["vcores"] = total_cores
            hadoop_resources[resource_type]["scheduler_maximum_memory"] = scheduler_maximum_memory
            hadoop_resources[resource_type]["scheduler_minimum_memory"] = scheduler_minimum_memory
            hadoop_resources[resource_type]["nodemanager_memory"] = nodemanager_memory
            hadoop_resources[resource_type]["map_memory"] = map_memory
            hadoop_resources[resource_type]["map_memory_java_opts"] = map_memory_java_opts
            hadoop_resources[resource_type]["reduce_memory"] = reduce_memory
            hadoop_resources[resource_type]["reduce_memory_java_opts"] = reduce_memory_java_opts
            hadoop_resources[resource_type]["mapreduce_am_memory"] = mapreduce_am_memory
            hadoop_resources[resource_type]["mapreduce_am_memory_java_opts"] = mapreduce_am_memory_java_opts
            print(hadoop_resources[resource_type])

    return

    setup_network_task = setup_containers_network_task.s(url, headers, app, app_files)
    start_containers_tasks = []

    # Start containers with app
    i = 0
    for host in new_containers:
        if "irregular" in new_containers[host]:
            # Start a chain of tasks so that containers of same host are started sequentially
            if i == 0:
                start_containers_tasks.append(chain(start_containers_with_app_task.s({},url, headers, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.s(url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])))
            else:
                start_containers_tasks.append(chain(start_containers_with_app_task.s(url, headers, host, new_containers[host]["irregular"], app, app_files, container_resources["irregular"]), start_containers_with_app_task.s(url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"])))

        else:
            if i == 0:
                start_containers_tasks.append(start_containers_with_app_task.s({},url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"]))
            else:
                start_containers_tasks.append(start_containers_with_app_task.s(url, headers, host, new_containers[host]["regular"], app, app_files, container_resources["regular"]))

        i += 1

    if len(start_containers_tasks) > 0:
        start_containers_tasks.append(setup_network_task)
        task = chain(*start_containers_tasks).delay()
        register_task(task.id,"setup_containers_network_task")

@shared_task
def setup_containers_network_task(app_containers, url, headers, app, app_files):

    # if chord worked:
    ## app_containers example = [{host0: ["host0-cont0","host0-cont1","host1-cont2"]}, {host1: ["host1-cont0"]}]
    # app_containers_dict = {}
    # for d in app_containers:
    #     app_containers_dict = mergeDictionary(app_containers_dict, d)

    # app_containers example = {'host0': ['host0-cont0', 'host0-cont1'], 'host1': ['host1-cont0', 'host1-cont1']}
    hosts = ','.join(list(app_containers.keys()))
    app_containers_dict = json.dumps(app_containers).replace(" ","")

    rc = subprocess.Popen([
        "./ui/scripts/setup_network_on_container.sh", hosts, app_containers_dict
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = rc.communicate()

    # Log ansible output
    print(out.decode("utf-8") )

    if rc.returncode != 0:
        error = "Error setting network for app {0}: {1}".format(app,err.decode("utf-8"))
        raise Exception(error)

    # Start app on containers
    for host in app_containers:
        for container in app_containers[host]:
            full_url = url + "container/{0}/{1}".format(container,app)
            add_container_to_app_task(full_url, headers, host, container, app, app_files)
            # Workaround to keep all updates to State DB
            time.sleep(0.5)

@shared_task
def add_container_to_app_task(full_url, headers, host, container, app, app_files):

    r = requests.put(full_url, headers=headers)

    error = ""
    if (r != "" and r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error adding container " + container + " to app " + app + ": " + soup.get_text().strip()

    if (error == ""):

        files_dir = app_files['files_dir']
        install_script = app_files['install_script']
        start_script = app_files['start_script']
        stop_script = app_files['stop_script']

        rc = subprocess.Popen(["./ui/scripts/start_app_on_container.sh", host, container, app, files_dir, install_script, start_script, stop_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = rc.communicate()

        # Log ansible output
        print(out.decode("utf-8") )

        if rc.returncode != 0:
            error = "Error starting app {0} on container {1}: {2}".format(app, container, err.decode("utf-8"))
            raise Exception(error)
    else:
        raise Exception(error)


def mergeDictionary(dict_1, dict_2):
   dict_3 = {**dict_1, **dict_2}
   for key, value in dict_3.items():
       if key in dict_1 and key in dict_2:
               dict_3[key] = value + dict_2[key]
   return dict_3

@shared_task
def start_containers_with_app_task(already_added_containers, url, headers, host, new_containers, app, app_files, container_resources):
    #TODO: merge function with start_containers_task

    if new_containers == 0:
        # Nothing to do
        return already_added_containers

    # update inventory file
    with lock:
        added_containers = add_containers_to_hosts({host: new_containers})

    added_formatted_containers = container_list_to_formatted_str(added_containers[host])

    # Start containers
    if app_files['install_script']:
        template_definition_file="app_container.def"
        definition_file = "{0}_container.def".format(app.replace(" ", "_"))
        image_file = "{0}_container.sif".format(app.replace(" ", "_"))
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

    rc = subprocess.Popen([
        "./ui/scripts/start_containers_with_app.sh", host, app, template_definition_file, definition_file, image_file, app_files['files_dir'], app_files['install_script'], added_formatted_containers, max_cpu_percentage_per_container, min_cpu_percentage_per_container, cpu_boundary, max_memory_per_container, min_memory_per_container, mem_boundary
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = rc.communicate()

    # Log ansible output
    print(out.decode("utf-8") )

    if rc.returncode != 0:
        error = "Error starting containers {0}: {1}".format(added_formatted_containers,err.decode("utf-8"))
        raise Exception(error)

    # # Start app on containers
    # for container in added_containers[host]:
    #     full_url = url + "container/{0}/{1}".format(container,app)
    #     add_container_to_app_task(full_url, headers, host, container, app, app_files)
    #     # Workaround to keep all updates to State DB
    #     time.sleep(0.5)

    return mergeDictionary(already_added_containers,added_containers)

@shared_task
def remove_container_task(full_url, headers, host_name, cont_name):

    r = requests.delete(full_url, headers=headers)

    error = ""
    if (r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error removing container " + cont_name + ": " + soup.get_text().strip()

    ## stop container
    if (error == ""):

        rc = subprocess.Popen(["./ui/scripts/stop_container.sh", host_name, cont_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = rc.communicate()

        # Log ansible output
        print(out.decode("utf-8") )

        if rc.returncode != 0:
            error = "Error stopping container {0}: {1}".format(cont_name,err.decode("utf-8"))
            raise Exception(error)

        # update inventory file
        with lock:
            remove_container_from_host(cont_name,host_name)
    else:
        raise Exception(error)

@shared_task
def remove_host_task(full_url, headers, host_name):

    r = requests.delete(full_url, headers=headers)
    
    error = ""
    if (r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error removing host " + host_name + ": " + soup.get_text().strip()

    ## remove host
    if (error == ""):
            
        # stop node scaler service in host
        rc = subprocess.Popen(["./ui/scripts/stop_host_scaler.sh", host_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = rc.communicate()

        # Log ansible output
        print(out.decode("utf-8") )

        if rc.returncode != 0:
            error = "Error stopping host {0} scaler service: {1}".format(host_name,err.decode("utf-8"))
            raise Exception(error)

        # update inventory file
        with lock:         
            remove_host(host_name)
    else:
        raise Exception(error)

@shared_task
def remove_app_task(url, structure_type_url, headers, app_name, container_list, app_files):

    # first, remove all containers from app
    for container in container_list:
        full_url = url + "container/{0}/{1}".format(container['name'], app_name)
        remove_container_from_app_task(full_url, headers, container['host'], container['name'], app_name, app_files)

    # then, actually remove app
    full_url = url + structure_type_url + "/" + app_name
    r = requests.delete(full_url, headers=headers)
    
    error = ""
    if (r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error removing app " + app_name + ": " + soup.get_text().strip()

    if (error == ""):
        pass
    else:
        raise Exception(error)

@shared_task
def remove_container_from_app_task(full_url, headers, host, container, app, app_files):

    r = requests.delete(full_url, headers=headers)

    error = ""
    if (r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error removing container " + container + " from app " + app + ": " + soup.get_text().strip()

    if (error == ""):

        files_dir = app_files['files_dir']
        install_script = app_files['install_script']
        start_script = app_files['start_script']
        stop_script = app_files['stop_script']

        rc = subprocess.Popen(["./ui/scripts/stop_app_on_container.sh", host, container, app, files_dir, install_script, start_script, stop_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = rc.communicate()

        # Log ansible output
        print(out.decode("utf-8") )

        if rc.returncode != 0:
            error = "Error stopping app {0} on container {1}: {2}".format(app, container, err.decode("utf-8"))
            raise Exception(error)

        if install_script != "":
            # remove container if it has been created specifically for this app
            # full_url[:full_url.rfind('/')] removes the last part of url -> .../container/host0-cont0/app1 -> .../container/host0-cont0
            remove_container_task(full_url[:full_url.rfind('/')], headers, host, container)

    else:
        raise Exception(error)