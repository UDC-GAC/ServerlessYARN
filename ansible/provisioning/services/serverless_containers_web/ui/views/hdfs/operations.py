import yaml
from django.conf import settings
from ui.utils import DEFAULT_RESOURCE_VALUES, DEFAULT_LIMIT_VALUES
from ui.background_tasks import register_task, get_pending_tasks_messages, stop_hdfs_task, remove_app_task, start_global_hdfs_task
from ui.views.core.utils import getDbData, getHostsNames, getScalerPollFreq, getDataAndFilterByApp, getContainersFromApp, getAppFiles

from serverlessyarn_utils.manage_inventory import AnsibleYamlInventory, HOST_CONTAINER_SEPARATOR

def start_global_hdfs(request, app_name, url, resources, nn_container_prefix, dn_container_prefix, webdriver_state):
    # Get host data
    data_json = getDbData(url)
    hosts = getHostsNames(data_json)
    containers = []

    # Container resources for HDFS cluster
    def_weight = DEFAULT_RESOURCE_VALUES['weight']
    def_boundary = DEFAULT_LIMIT_VALUES['boundary']
    def_boundary_type = DEFAULT_LIMIT_VALUES["boundary_type"]

    resource_config_file = str(settings.BASE_DIR) + "/../../apps/base/global_hdfs/resource_config.yml"
    with open(resource_config_file, "r") as f: hdfs_container_resources = yaml.load(f, Loader=yaml.FullLoader)

    ## Load default values
    for node_type in hdfs_container_resources:
        for resource in hdfs_container_resources[node_type]:
            node_res = hdfs_container_resources[node_type][resource]
            if node_res["weight"]        == "default": node_res["weight"]        = def_weight
            if node_res["boundary"]      == "default": node_res["boundary"]      = def_boundary
            if node_res["boundary_type"] == "default": node_res["boundary_type"] = def_boundary_type

    if len(hosts) > 0:
        ## Create NameNode
        if settings.PLATFORM_CONFIG['server_as_host']:
            # the namenode must be deployed on the server
            inventory = AnsibleYamlInventory()
            server_name = inventory.get_server_hostname()

            for h in hosts:
                if server_name == h['name']:
                    host = h
                    break
        else:
            # just choose the first node otherwise
            host = hosts[0]

        container = {}
        container["container_name"] = nn_container_prefix + HOST_CONTAINER_SEPARATOR + host['name']
        container["host"] = host['name']
        for resource in ["cpu", "mem"]:
            for key in ["max", "min", "weight", "boundary", "boundary_type"]:
                container[f"{resource}_{key}"] = hdfs_container_resources['namenode'][resource][key]

        # Disk
        if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling'] and 'disks' in host["resources"] and len(host["resources"]['disks']) > 0:
            if settings.PLATFORM_CONFIG['global_hdfs_disk_name'] in host["resources"]["disks"]:
                disk = settings.PLATFORM_CONFIG['global_hdfs_disk_name']
                container["disk"] = disk
                container['disk_path'] = host["resources"]['disks'][disk]["path"]
                for res in ["disk_read", "disk_write"]:
                    if "max" in hdfs_container_resources['namenode'][res]:
                        container[f"{res}_max"] = hdfs_container_resources['namenode'][res]["max"]
                    else:
                        container[f"{res}_max"] = host["resources"]['disks'][disk][f"max_{res[5:]}"]
                    for key in ["min", "weight", "boundary", "boundary_type"]:
                        container[f"{res}_{key}"] = hdfs_container_resources['namenode'][res][key]

        containers.append(container)

    for host in hosts:
        ## Create DataNodes
        if settings.PLATFORM_CONFIG['server_as_host'] and settings.PLATFORM_CONFIG['reserve_server_for_master']:
            # Do not create a datanode in the server node if it is reserved for master containers
            if host['name'] == server_name: continue

        container = {}
        container["container_name"] = dn_container_prefix + HOST_CONTAINER_SEPARATOR + host['name']
        container["host"] = host['name']
        for resource in ["cpu", "mem"]:
            for key in ["max", "min", "weight", "boundary", "boundary_type"]:
                container[f"{resource}_{key}"] = hdfs_container_resources['datanode'][resource][key]
        # Disk
        if settings.PLATFORM_CONFIG['disk_capabilities'] and settings.PLATFORM_CONFIG['disk_scaling'] and 'disks' in host["resources"] and len(host["resources"]['disks']) > 0:
            disk = next((d for d in host["resources"]["disks"] if d != settings.PLATFORM_CONFIG['global_hdfs_disk_name']), None) ## avoid getting the frontend global hdfs disk
            container["disk"] = disk
            container['disk_path'] = "/".join([host["resources"]['disks'][disk]["path"], settings.VARS_CONFIG['bind_dir_name'], container["container_name"]])
            for res in ["disk_read", "disk_write"]:
                if "max" in hdfs_container_resources['datanode'][res]:
                    container[f"{res}_max"] = hdfs_container_resources['datanode'][res]["max"]
                else:
                    container[f"{res}_max"] = host["resources"]['disks'][disk][f"max_{res[5:]}"]
                for key in ["min", "weight", "boundary", "boundary_type"]:
                    container[f"{res}_{key}"] = hdfs_container_resources['datanode'][res][key]

        containers.append(container)

    if len(containers) == 0: raise Exception("Cannot create any containers for HDFS cluster")

    virtual_cluster = settings.PLATFORM_CONFIG['virtual_mode']
    app_name = settings.VARS_CONFIG['global_hdfs_app_name']
    app_directory = "apps/" + app_name
    url = url + "apps/" + app_name

    ## APP info
    app_files = {}
    app_files['app_dir'] = "base/" + app_name
    app_files['app_type'] = "hadoop_app"
    app_files['runtime_files'] = "runtime_files"
    for key in ['start_script', 'stop_script', 'install_script', 'install_files', 'output_dir']: app_files[key] = ""

    put_field_data = {
        'app': {
            'name': app_name,
            'resources': {},
            'guard': False,
            'subtype': "application",
            'install_script': "",
            'start_script': "",
            'stop_script': "",
            'install_files': "",
            'runtime_files': app_files['runtime_files'],
            'output_dir': "", ## actually I might use this to store logs
            'framework': "hadoop"
        },
        'limits': {'resources': {}}
    }

    for resource in resources:
        resource_max = 0
        resource_min = 0

        for container in containers:
            if "{0}_max".format(resource) in container and "{0}_min".format(resource) in container:
                resource_max += container["{0}_max".format(resource)]
                resource_min += container["{0}_min".format(resource)]

        put_field_data['app']['resources'][resource] = {'max': resource_max, 'min': resource_min, 'guard': 'false'}
        put_field_data['app']['resources'][resource]['weight'] = def_weight
        put_field_data['limits']['resources'][resource] = {'boundary': def_boundary, 'boundary_type': def_boundary_type}

    webdriver_state.__start_webdriver__()

    task = start_global_hdfs_task.delay(url, app_name, app_files, containers, virtual_cluster, put_field_data, hosts)
    print("Starting task with id {0}".format(task.id))
    register_task(task.id, "{0}_app_task".format(app_name))

    error = ""
    return error


def stop_global_hdfs(request, app_name, url, resources, nn_container_prefix, webdriver_state):
    data, app = getDataAndFilterByApp(url, app_name)
    container_list = getContainersFromApp(data, app)
    app_files = getAppFiles(app)
    scaler_polling_freq = getScalerPollFreq()

    rm_host = None
    rm_container = None
    for container in container_list:
        if nn_container_prefix in container['name']:
            rm_container = container['name']
            rm_host = container['host']
            break

    webdriver_state.__stop_webdriver__()

    error = ""
    if not rm_container:
        error = "Missing namenode container on hdfs app"
        # Just remove the app and its containers
        task = remove_app_task.delay(url, "apps", app_name, container_list, app_files)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"remove_app_task")
    else:
        # First stop the cluster and then remove the app and its containers
        task = stop_hdfs_task.delay(url, app_name, app_files, container_list, scaler_polling_freq, rm_host, rm_container)
        print("Starting task with id {0}".format(task.id))
        register_task(task.id,"stop_hdfs_task")

    return error