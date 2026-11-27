## Big Data (Hadoop / Spark / HDFS) specific background tasks
## Registered in Celery along with the generic ones in ui/background/tasks.py (see serverless_containers_web/celery.py)

import time
import timeit

from celery import shared_task

from django.conf import settings

from ui.domain.state_db import getDbData
from ui.domain.structures import getHostsNames
from ui.domain.update_inventory_file import add_containers_to_inventory
import ui.domain.run_playbooks as run_playbooks
from ui.background.tasks import (redis_server, lock_key, register_task, update_task_runtime, create_app_counter, scaling_services_disabled,
                                 add_app_task, change_app_state_in_db, enable_container_guard_in_db, deploy_app_containers, wait_for_app_dependency,
                                 start_app_on_container_task, wait_for_app_on_container_task, get_container_deployment_info,
                                 remove_app_from_db, remove_app_containers_from_db, stop_app_on_containers)

import ui.bigdata.playbooks as bigdata_playbooks
from ui.bigdata.resources import set_hadoop_resources
from ui.bigdata.data_locality import record_deployment, clear_registry


## Hadoop apps
@shared_task(bind=True)
def start_hadoop_app_task(self, assignation_requirements, url, app, app_files, container_resources, scaler_polling_freq, virtual_cluster, app_type="hadoop_app", global_hdfs_data=None, dependencies={}):

    new_containers, disk_assignation = wait_for_app_dependency(assignation_requirements, url, app, container_resources, dependencies)

    if settings.PLATFORM_CONFIG['enable_app_callback']:
        raise Exception("Callback app execution not currently supported by hadoop apps")

    ## Create redis counter to track the containers' status
    create_app_counter(app, 1)

    # Calculate resources for Hadoop cluster
    hadoop_resources = {}
    for container_type in ["regular", "irregular"]:
        # NOTE: 'irregular' container won't be created due to a previous workaround
        if container_type in container_resources:

            number_of_workers = 0
            for host in new_containers:
                if container_type in new_containers[host]: number_of_workers += new_containers[host][container_type]

            replication_factor = settings.PLATFORM_CONFIG['local_hdfs_replication'] if settings.PLATFORM_CONFIG['hdfs_mode'] != 'single' else settings.PLATFORM_CONFIG['global_hdfs_replication']
            hadoop_resources[container_type] = set_hadoop_resources(container_resources[container_type], virtual_cluster, number_of_workers, replication_factor=replication_factor)

    start_time = timeit.default_timer()

    # Set application in running state in ServerlessContainers
    change_app_state_in_db(url, app, "running")

    app_containers = deploy_app_containers(url, new_containers, app, app_files, container_resources, disk_assignation, app_type)

    # Keep track of where the app has been deployed to guide future deployments using the Data-locality policy
    if global_hdfs_data:
        deployment_info = {
            "assignation_policy": assignation_requirements['assignation_policy'],
            "locality_source": assignation_requirements.get('data_locality', {}).get('source'),
            "dependency_app": dependencies.get("app"),
            "hdfs_mode": settings.PLATFORM_CONFIG['hdfs_mode'],
            "global_input": global_hdfs_data.get("global_input"),
            "global_output": global_hdfs_data.get("global_output")
        }
        try:
            record_deployment(app, new_containers, deployment_info)
        except Exception as e:
            print("[DATA LOCALITY] Error recording deployment of app {0}: {1}".format(app, str(e)))

    master_container = get_master_container(app, app_containers)

    download_time, upload_time = setup_containers_hadoop_network_task(app_containers, master_container, url, app, app_files, hadoop_resources, new_containers, app_type, global_hdfs_data)
    master_host = master_container['host']

    end_time = timeit.default_timer()
    runtime = "{:.2f}".format(end_time-start_time)
    update_task_runtime(self.request.id, runtime)

    # Stop hadoop cluster, set app as stopped, persist output data and remove containers
    errors = stop_hadoop_app(url, app, app_files, app_containers, scaler_polling_freq, master_host, master_container['container_name'],
                             download_time=download_time, upload_time=upload_time)

    if len(errors) > 0: raise Exception(str(errors))


def get_master_container(app, app_containers):
    """
    Return the master container of a Hadoop app from the containers deployed by deploy_app_containers,
    which tags each container with the 'role' it was created for ('master', 'irregular' or 'regular').
    """
    masters = [container for container in (app_containers or []) if container.get('role') == 'master']
    if len(masters) != 1:
        raise Exception("Expected exactly one master container for app {0}, found {1}. Containers: {2}".format(app, len(masters), app_containers))
    return masters[0]


@shared_task
def setup_containers_hadoop_network_task(app_containers, master_container, url, app, app_files, hadoop_resources, new_containers, app_type="hadoop_app", global_hdfs_data=None):

    app_files['app_type'] = app_type
    master_host = master_container['host']

    # app_containers example = [{'container_name':'host1-cont0','host':'host1','cpu_max':200,'disk':'ssd_0',...},{'container_name':'host2-cont0','host':'host2',...}]
    formatted_app_containers = str(app_containers).replace(' ','')

    download_time, upload_time = 0,0
    # Setup network and hadoop on containers (containers are not guarded yet, so they are not scaled during the setup)
    if not global_hdfs_data:
        bigdata_playbooks.setup_hadoop_network_on_containers(list(new_containers.keys()), app, app_files, formatted_app_containers, master_host, master_container['container_name'], hadoop_resources["regular"])
    else:
        bigdata_playbooks.setup_hadoop_network_with_global_hdfs(list(new_containers.keys()), app, app_files, formatted_app_containers, master_host, master_container['container_name'], hadoop_resources["regular"], global_hdfs_data)

    # Containers are ready, allow them to be scaled from now on (data transfers and app execution)
    for container in app_containers:
        enable_container_guard_in_db(url, container['container_name'])

    ## Download required input data from global HDFS to local one
    if global_hdfs_data and global_hdfs_data.get("global_input", "") != "":
        change_app_state_in_db(url, app, "hdfs_downloading")
        download_time = bigdata_playbooks.download_global_hdfs_data_to_local(master_host, master_container['container_name'], global_hdfs_data, formatted_app_containers)
        change_app_state_in_db(url, app, "running")

    # Lastly, start app on master container
    full_url = url + "container/{0}/{1}".format(master_container['container_name'],app)
    start_app_on_container_task(full_url, master_host, master_container, app, app_files, global_hdfs_data)

    # Wait for master container to finish
    wait_for_app_on_container_task(master_host, master_container, app)

    if global_hdfs_data:
        ## Upload generated output data from local HDFS to global one
        change_app_state_in_db(url, app, "hdfs_uploading")
        upload_time = bigdata_playbooks.upload_local_hdfs_data_to_global(master_host, master_container['container_name'], global_hdfs_data, formatted_app_containers)

    return download_time, upload_time

## HDFS operations
@shared_task(bind=True)
def create_dir_on_hdfs(self, namenode_host, namenode_container, dir_to_create):
    bigdata_playbooks.create_dir_on_hdfs(namenode_host, namenode_container, dir_to_create)

@shared_task(bind=True)
def add_file_to_hdfs(self, namenode_host, namenode_container, file_to_add, dest_path):
    if settings.PLATFORM_CONFIG["server_as_host"]:
        frontend_container = namenode_container
    else:
        frontend_container = settings.VARS_CONFIG["hdfs_frontend_container_name"]

    bigdata_playbooks.add_file_to_hdfs(namenode_host, namenode_container, file_to_add, dest_path, frontend_container)

@shared_task(bind=True)
def get_file_from_hdfs(self, namenode_host, namenode_container, file_to_download, dest_path):
    if settings.PLATFORM_CONFIG["server_as_host"]:
        frontend_container = namenode_container
    else:
        frontend_container = settings.VARS_CONFIG["hdfs_frontend_container_name"]

    bigdata_playbooks.get_file_from_hdfs(namenode_host, namenode_container, file_to_download, dest_path, frontend_container)

@shared_task(bind=True)
def remove_file_from_hdfs(self, namenode_host, namenode_container, path_to_delete):
    bigdata_playbooks.remove_file_from_hdfs(namenode_host, namenode_container, path_to_delete)

## Global HDFS
@shared_task(bind=True)
def monitor_global_hdfs_replication(self, global_app_name, global_namenode_host, global_namenode_name):

    def reload_db_info(global_app_url, global_namenode_url):
        ## Global app
        global_app = getDbData(global_app_url)
        global_namenode = getDbData(global_namenode_url)

        ## Hosts
        if global_app and "disk" in global_app["resources"]:
            data_json = getDbData("/".join([settings.BASE_URL, "structure", ""])) ## the url needs to end with "/"
            hosts = getHostsNames(data_json)

        return global_app, global_namenode, hosts

    ## TODO: make the polling frequency and thresholds dynamically configurable variables from the interface
    polling_frequency = 30
    threshold = 0.15
    read_threshold = threshold
    write_threshold = threshold

    global_app_url = "/".join([settings.BASE_URL, "structure", global_app_name ])
    global_namenode_url = "/".join([settings.BASE_URL, "structure", global_namenode_name ])

    ## HDFS has just started, wait until next polling period
    time.sleep(polling_frequency)

    ## Reload DB info
    global_app, global_namenode, hosts = reload_db_info(global_app_url, global_namenode_url)

    ## Get disks used by global HDFS
    datanode_list = {}
    if global_app and "disk" in global_app["resources"]:
        for host in hosts:
            datanode_list[host['name']] = []

        for container_name in global_app['containers']:
            if container_name != global_namenode_name:
                container = getDbData("/".join([settings.BASE_URL, "structure", container_name ]))
                if "disk" in container['resources']:
                    datanode_list[container['host']].append(container)

    ## Loop until global HDFS is stopped
    while bool(global_app) and bool(global_namenode) and global_namenode['name'] in global_app['containers']:

        run_replication = True
        for host in hosts:
            for datanode in datanode_list[host['name']]:
                match_disk = None
                for host_disk in host['resources']['disks']:
                    if host_disk == datanode['resources']['disk']['name']:
                        match_disk = host['resources']['disks'][host_disk]
                        break
                if not match_disk: raise Exception("Disk {0} not found in host {1}. Host data: {2}".format(datanode['resources']['disk']['name'], host['name'], host))
                if any(
                    (match_disk[f'max_{res}'] - datanode['resources'][f"disk_{res}"]['min']) * thresh < match_disk[f'max_{res}'] - datanode['resources'][f"disk_{res}"]['min'] - match_disk[f'free_{res}'] 
                    or global_app["resources"][f"disk_{res}"]["max"] * thresh < global_app["resources"][f"disk_{res}"]["usage"] 
                    for res, thresh in [("read", read_threshold), ("write", write_threshold)]
                ):
                    run_replication = False
                    break

        if run_replication:
            ## Check all app usage for that
            ## Enforce HDFS replication only if global cluster has low I/O usage (at least below the threshold)
            bigdata_playbooks.set_global_hdfs_replication(global_namenode_host, global_namenode_name, settings.PLATFORM_CONFIG['global_hdfs_replication'])

        time.sleep(polling_frequency)
        global_app, global_namenode, hosts = reload_db_info(global_app_url, global_namenode_url)

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

    hdfs_resources = set_hadoop_resources(worker_resources, virtual_cluster, number_of_workers, replication_factor=settings.PLATFORM_CONFIG['global_hdfs_replication'])

    start_time = timeit.default_timer()

    ## Create HDFS app
    add_app_task(url, put_field_data, app, app_files)

    ## Create and start containers
    # update inventory file
    with redis_server.lock(lock_key):
        add_containers_to_inventory(containers)

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
                container['expose_ptp'] = 1
                container['portmap'] = "portmap={0}:{1}/tcp".format(settings.PLATFORM_CONFIG['local_namenode_port'], settings.PLATFORM_CONFIG['namenode_port'])
            break
    if not nn_container: raise Exception("Namenode container not found in container list") # should not happen

    host_list = []
    for host in hosts: host_list.append(host['name'])
    formatted_containers_info = str(containers).replace(' ','')

    # Start containers
    with scaling_services_disabled():
        run_playbooks.start_containers_with_app(host_list, formatted_containers_info, app, app_files['app_type'], app_files)

    ## Setup network and start HDFS
    # Run HDFS + YARN on the global HDFS cluster, thus distcp may be run within the global cluster
    start_zookeeper = settings.PLATFORM_CONFIG['hdfs_mode'] == 'rbf'
    bigdata_playbooks.setup_hadoop_network_on_containers(host_list, app, app_files, formatted_containers_info, nn_host, nn_container, hdfs_resources, start_zookeeper=start_zookeeper)

    # Start hdfs frontend container
    if not settings.PLATFORM_CONFIG["server_as_host"]:
        bigdata_playbooks.start_hdfs_frontend(host_list, "hdfs_frontend", formatted_containers_info, nn_host, nn_container)

    ## Run the replication factor monitor
    if settings.PLATFORM_CONFIG["hdfs_replication_mode"] == "monitor":
        monitor_task = monitor_global_hdfs_replication.delay(app, nn_host, nn_container)
        register_task(monitor_task.id,"monitor_hdfs_task")

    end_time = timeit.default_timer()
    runtime = "{:.2f}".format(end_time-start_time)
    update_task_runtime(self.request.id, runtime)

@shared_task(bind=True)
def stop_hdfs_task(self, url, app, app_files, app_containers, scaler_polling_freq, master_host, master_container):

    # Containers come from StateDB, so convert them to the same format used when deploying apps
    app_containers = [get_container_deployment_info(container) for container in app_containers]

    # Same workflow as Hadoop apps: stop cluster, persist HDFS logs and remove containers. Additionally:
    ## - The app is removed from StateDB, as the global HDFS app is created each time the cluster is started
    ## - The NameNode bind directory is kept, as it may be a disk directly used by the server (e.g., when the server is used as host)
    ##   Removing the datanodes bind directories also cleans their data dirs, avoiding errors when creating a new global HDFS cluster
    errors = stop_hadoop_app(url, app, app_files, app_containers, scaler_polling_freq, master_host, master_container,
                             keep_bind_dir=[master_container], remove_app=True)

    ## Previous deployments are no longer close to any data, as global HDFS data has been removed
    try:
        clear_registry()
    except Exception as e:
        print("[DATA LOCALITY] Error clearing deployment registry: {0}".format(str(e)))

    # Stop hdfs frontend container
    if not settings.PLATFORM_CONFIG["server_as_host"]:
        run_playbooks.stop_container("platform_server", settings.VARS_CONFIG['hdfs_frontend_container_name'])

    if len(errors) > 0: raise Exception(str(errors))


## Stop workflows
def stop_hadoop_app(url, app, app_files, app_containers, scaler_polling_freq, master_host, master_container, download_time=0, upload_time=0, keep_bind_dir=None, remove_app=False):
    """
    Stop workflow shared by Hadoop apps and the global HDFS cluster:
      1. Gracefully stop the Hadoop cluster (HDFS + YARN) from the master container
      2. Remove the containers from StateDB, and then set the app as stopped (or remove it if 'remove_app' is set)
      3. Stop the app on each container, persist output data (including Hadoop logs) and stop the containers
      4. Remove the app DNS entries
    Returns a list with the errors found.
    """
    bigdata_playbooks.stop_hadoop_cluster(master_host, master_container)

    errors = remove_app_containers_from_db(url, app, app_containers, scaler_polling_freq, app_state=None if remove_app else "stopped")
    if remove_app:
        error = remove_app_from_db(url, app)
        if error: errors.append(error)

    errors += stop_app_on_containers(app, app_files, app_containers, master_container, download_time, upload_time, keep_bind_dir)

    return errors
