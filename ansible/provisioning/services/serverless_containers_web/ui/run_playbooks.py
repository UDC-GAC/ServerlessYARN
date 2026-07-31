#!/usr/bin/python

from celery import shared_task
import yaml
import logging
import sys

logger = logging.getLogger(__name__)

from serverlessyarn_utils.manage_ansible import run_playbook, run_adhoc, PROVISION_DIR
vars_path = f"{PROVISION_DIR}/vars/main.yml"
config_path =  f"{PROVISION_DIR}/config/config.yml"

# Auxiliary
def check_container_bind_path(container, bind_path):
    if bind_path:
        return bind_path

    with open(vars_path, "r") as vars_file:
        vars_config = yaml.load(vars_file, Loader=yaml.FullLoader)
        return "/".join([vars_config['bind_dir'], container])


# Call playbook tasks
## Manage hosts
def configure_host(host_name):
    run_playbook(playbook_name="install_playbook.yml", limit=[host_name])
    run_playbook(playbook_name="start_containers_playbook.yml", limit=[host_name,"localhost"])
    run_playbook(playbook_name="launch_playbook.yml", tags=["add_hosts", "start_containers"])

### Disks
def add_disks(host_names, new_disks):
    run_playbook(playbook_name="install_playbook.yml", tags=["add_disks"], limit=host_names, extravars={"new_disks_dict_str": new_disks})
    run_playbook(playbook_name="launch_playbook.yml", tags=["add_disks"], extravars={"new_disks_dict_str": new_disks})

@shared_task
def extend_lv(host_names, new_disks, extra_disk, measure_host_list, throttle_containers_bw=False):
    ## External Python script
    sys.path.append(f"{PROVISION_DIR}/scripts")
    import state_database.limit_containers_bw as limit_containers_bw

    # We disable services that may generate scaling requests and cap bandwidth of running containers to speed up the extension process
    if throttle_containers_bw:
        manage_scaling_services(enable=False)
        limit_containers_bw.main(str(host_names), config_path)

    run_playbook(playbook_name="install_playbook.yml", tags=["extend_lv"], limit=host_names, extravars={
        "new_disks_list": new_disks,
        "extra_disk": extra_disk,
        "measure_host_list_str": measure_host_list
    })

    run_playbook(playbook_name="launch_playbook.yml", tags=["extend_lv"], extravars={"host_list": ",".join(host_names)})

    # Re-enable disabled services
    if throttle_containers_bw:
        manage_scaling_services(enable=True)
        limit_containers_bw.main(str(host_names), config_path)

## Manage containers
def start_containers(host_names, containers_info):
    run_playbook(playbook_name="start_containers_playbook.yml", tags=["start_containers"], limit=(host_names + ["localhost"]), extravars={"host_list": ",".join(host_names), "containers_info_str": containers_info})
    run_playbook(playbook_name="launch_playbook.yml", tags=["start_containers"], extravars={"host_list": ",".join(host_names), "containers_info_str": containers_info})

def start_containers_with_app(host_names, containers_info, app_name, app_type, app_files):

    extravars = {
        "host_list": ",".join(host_names),
        "containers_info_str": containers_info,
        "app_type": app_type
    }
    extravars.update(app_files)

    run_playbook(playbook_name="start_containers_playbook.yml", tags=["start_containers"], limit=(host_names + ["localhost"]), extravars=extravars)
    run_playbook(playbook_name="launch_playbook.yml", tags=["start_containers"], extravars={"host_list": host_names, "containers_info_str": containers_info, "app_name": app_name})

def stop_container(host_name, container, bind_path=None, clean_bind_dir=True):

    with open(config_path, "r") as config_file: config = yaml.load(config_file, Loader=yaml.FullLoader)

    container_engine = config["container_engine"]
    singularity_command_alias = config["singularity_command_alias"]
    cgroups_version = config["cgroups_version"]

    # Stop container
    if container_engine == "lxc":
        run_adhoc(hosts=[host_name], module="shell", module_args="lxc stop {0} || lxc stop -f {0}".format(container), ignore_failure=True)
    elif container_engine == "apptainer":
        # if cgroups_version == "v1": Used to run without sudo in cgroups V2, currently both versions run this command with root privileges
        stop_cmd = "sudo {0} instance stop {1} || sudo {0} instance stop -f {1}".format(singularity_command_alias, container)
        run_adhoc(hosts=[host_name], module="shell", module_args=stop_cmd, ignore_failure=True)
    else:
        raise Exception("No valid container engine")

    # Remove bind directory
    if clean_bind_dir:
        with open(vars_path, "r") as vars_file: vars_config = yaml.load(vars_file, Loader=yaml.FullLoader)
        bind_path = check_container_bind_path(container, bind_path)

        run_adhoc(hosts=[host_name], module="file", module_args="path={0} state=absent".format(bind_path), extravars=vars_config)

def setup_network_on_containers(host_names, containers_info, app_name):
    run_playbook(playbook_name="manage_app_on_container.yml",
                 tags=["setup_network"],
                 limit=host_names,
                 extravars={"containers_info_str": containers_info, "app_name": app_name})


## Manage applications
def create_app(app_files):
    run_playbook(playbook_name="start_containers_playbook.yml", tags=["create_app"], extravars=app_files)

def start_app_on_container(host_name, container, app_name, app_files, bind_path=None, global_hdfs_data=None):

    bind_path = check_container_bind_path(container, bind_path)

    extravars = {
        "container": container,
        "app_name": app_name,
        "container_bind_dir": bind_path
    }
    extravars.update(app_files)
    if global_hdfs_data: extravars.update(global_hdfs_data)

    run_playbook(playbook_name="manage_app_on_container.yml", tags=["start_app"], limit=[host_name], extravars=extravars)

def wait_for_app_on_container(host_name, container):
    extravars = {"container": container}
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["wait_app"], limit=[host_name], extravars=extravars)

def stop_app_on_container(host_name, container, app_name, app_files, rm_container, bind_path=None, timestamp=None, download_time=0, upload_time=0):

    bind_path = check_container_bind_path(container, bind_path)

    extravars = {
        "container": container,
        "app_name": app_name,
        "container_bind_dir": bind_path,
        "rm_container": rm_container,
        "timestamp": timestamp,
        "download_time": download_time,
        "upload_time": upload_time
    }
    extravars.update(app_files)

    run_playbook(playbook_name="manage_app_on_container.yml", tags=["stop_app"], limit=[host_name], extravars=extravars)


## Manage services
def disable_scaler():
    run_playbook(playbook_name="manage_scaling_services.yml", tags=["disable_scaler"])

def enable_scaler():
    run_playbook(playbook_name="manage_scaling_services.yml", tags=["enable_scaler"])

def manage_scaling_services(enable):
    if enable:
        run_playbook(playbook_name="manage_scaling_services.yml", tags=["enable_scaling_services"])
    else:
        run_playbook(playbook_name="manage_scaling_services.yml", tags=["disable_scaling_services"])

def stop_host_scaler(host_name):
    run_playbook(playbook_name="stop_services_playbook.yml", tags=["stop_node_scaler"], limit=[host_name])


## Hadoop
def setup_hadoop_network_on_containers(host_names, app_name, app_files, containers_info, rm_host, rm_container, hadoop_conf, start_zookeeper=False):
    extravars = {
        "app_name": app_name,
        "containers_info_str": containers_info,
        "rm_host": rm_host,
        "rm_container": rm_container
    }
    extravars.update(app_files)
    extravars.update(hadoop_conf)
    tags = ["setup_network", "setup_hadoop"]
    if start_zookeeper: tags.append("start_zookeeper")
    if app_name == "global_hdfs": tags.append("copy_files")

    run_playbook(playbook_name="manage_app_on_container.yml", tags=tags, limit=host_names, extravars=extravars)

def stop_hadoop_cluster(rm_host, rm_container):
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["stop_hadoop_cluster"], limit=[rm_host], extravars={"rm_host": rm_host, "rm_container": rm_container})


## HDFS
def setup_hdfs_network(host_names, app_name, app_type, containers_info, rm_host, rm_container, hdfs_resources):

    extravars = {
        "app_name": app_name,
        "app_type": app_type,
        "containers_info_str": containers_info,
        "rm_host": rm_host,
        "rm_container": rm_container
    }
    extravars.update(hdfs_resources)

    run_playbook(playbook_name="manage_app_on_container.yml", tags=["setup_network", "setup_hdfs"], limit=host_names, extravars=extravars)

def start_hdfs_frontend(host_names, app_type, containers_info, nn_host, nn_container):

    extravars = {
        "app_type": app_type,
        "containers_info_str": containers_info,
        "nn_host": nn_host,
        "nn_container": nn_container
    }

    run_playbook(playbook_name="start_containers_playbook.yml", tags=["setup_hdfs"], limit=host_names, extravars=extravars)

def create_dir_on_hdfs(host_name, namenode_container, dir_to_create):
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["create_dir_on_hdfs"], limit=[host_name], extravars={"container": namenode_container, "dest_path": dir_to_create})

def remove_file_from_hdfs(host_name, namenode_container, path_to_remove):
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["remove_file_from_hdfs"], limit=[host_name], extravars={"container": namenode_container, "dest_path": path_to_remove})

def add_file_to_hdfs(host_name, namenode_container, file_to_add, dest_path, frontend_container):
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["add_file_to_hdfs"], limit=[host_name], extravars={
        "namenode_container": namenode_container,
        "origin_path": file_to_add,
        "dest_path": dest_path,
        "frontend_container": frontend_container
    })

def get_file_from_hdfs(host_name, namenode_container, file_to_download, dest_path, frontend_container):
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["get_file_from_hdfs"], limit=[host_name], extravars={
        "namenode_container": namenode_container,
        "origin_path": file_to_download,
        "dest_path": dest_path,
        "frontend_container": frontend_container
    })

def setup_hadoop_network_with_global_hdfs(host_names, app_name, app_files, containers_info, rm_host, rm_container, hadoop_conf, global_hdfs_data):

    extravars = {
        "app_name": app_name,
        "containers_info_str": containers_info,
        "rm_host": rm_host,
        "rm_container": rm_container
    }
    extravars.update(app_files)
    extravars.update(hadoop_conf)
    extravars.update(global_hdfs_data)

    tags = ["setup_network", "setup_global_hdfs_connection", "setup_hadoop", "download_to_local"]

    _, task_timings = run_playbook(playbook_name="manage_app_on_container.yml", tags=tags, limit=(host_names + [global_hdfs_data["namenode_host"]]), extravars=extravars)

    transfer_time = 0
    if 'Get input data' in task_timings: transfer_time += task_timings['Get input data']
    if 'Put input data into target HDFS' in task_timings: transfer_time += task_timings['Put input data into target HDFS']
    if 'Remove file in temporary location' in task_timings: transfer_time += task_timings['Remove file in temporary location']
    if 'Transfer data' in task_timings: transfer_time += task_timings['Transfer data']
    return transfer_time

def upload_local_hdfs_data_to_global(rm_host, rm_container, global_hdfs_data, containers_info):

    extravars = {
        "rm_host": rm_host,
        "rm_container": rm_container,
        "containers_info_str": containers_info
    }
    extravars.update(global_hdfs_data)

    _, task_timings = run_playbook(playbook_name="manage_app_on_container.yml", tags=["upload_to_global"], limit=[global_hdfs_data['namenode_host']], extravars=extravars)
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["remove_global_hdfs_connection"], extravars=extravars)

    transfer_time = 0
    if 'Get input data' in task_timings: transfer_time += task_timings['Get input data']
    if 'Put input data into target HDFS' in task_timings: transfer_time += task_timings['Put input data into target HDFS']
    if 'Remove file in temporary location' in task_timings: transfer_time += task_timings['Remove file in temporary location']
    if 'Transfer data' in task_timings: transfer_time += task_timings['Transfer data']
    return transfer_time

def clean_hdfs(host_name, container):
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["clean_hdfs"], limit=[host_name], extravars={"container": container})

def set_global_hdfs_replication(nn_host, nn_container, replication_factor):

    extravars = {
        "namenode_host": nn_host,
        "namenode_container_name": nn_container,
        "replication_factor": replication_factor
    }

    _, task_timings = run_playbook(playbook_name="manage_app_on_container.yml", tags=["set_hdfs_replication"], limit=[nn_host], extravars=extravars)

    replication_time = 0
    if 'Set global HDFS replication' in task_timings: replication_time += task_timings['Set global HDFS replication']
    logger.info(f"\n{'#'*80}\nGlobal HDFS replication took {replication_time} seconds\n{'#'*80}")

def get_hdfs_filesystem(namenode_host, namenode_container_name):

    extravars = {
        "namenode_host": namenode_host,
        "namenode_container_name": namenode_container_name,
    }

    output, _ = run_playbook(playbook_name="manage_app_on_container.yml", tags=["get_hdfs_filesystem"], limit=[namenode_host], extravars=extravars)

    ## Access to listed files
    task_name = "Get HDFS filesystem"
    output_key = "{0}_stdout".format(task_name)
    return output[output_key]

def drop_host_caches():
    run_playbook(playbook_name="start_containers_playbook.yml", tags=["drop_caches"])
