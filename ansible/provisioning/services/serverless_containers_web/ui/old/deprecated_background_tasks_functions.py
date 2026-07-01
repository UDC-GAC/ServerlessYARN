import subprocess
import timeit
import redis
from celery import shared_task, chain

redis_server = redis.StrictRedis()
lock_key = "ansible_inventory_access_lock"

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