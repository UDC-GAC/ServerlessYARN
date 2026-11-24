#!/usr/bin/python

import logging

logger = logging.getLogger(__name__)

from serverlessyarn_utils.manage_ansible import run_playbook

## Big Data (Hadoop / Spark / HDFS) specific calls to Ansible playbooks

## Hadoop
def setup_hadoop_network_on_containers(host_names, app_name, app_files, containers_info, master_host, master_container, hadoop_conf, start_zookeeper=False):
    extravars = {
        "app_name": app_name,
        "containers_info_str": containers_info,
        "master_host": master_host,
        "master_container": master_container
    }
    extravars.update(app_files)
    extravars.update(hadoop_conf)
    tags = ["setup_network", "setup_hadoop"]
    if start_zookeeper: tags.append("start_zookeeper")
    if app_name == "global_hdfs": tags.append("copy_files")

    run_playbook(playbook_name="manage_app_on_container.yml", tags=tags, limit=host_names, extravars=extravars)

def stop_hadoop_cluster(master_host, master_container):
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["stop_hadoop_cluster"], limit=[master_host], extravars={"master_host": master_host, "master_container": master_container})


## HDFS
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

def setup_hadoop_network_with_global_hdfs(host_names, app_name, app_files, containers_info, master_host, master_container, hadoop_conf, global_hdfs_data):

    extravars = {
        "app_name": app_name,
        "containers_info_str": containers_info,
        "master_host": master_host,
        "master_container": master_container
    }
    extravars.update(app_files)
    extravars.update(hadoop_conf)
    extravars.update(global_hdfs_data)

    tags = ["setup_network", "setup_hadoop"]

    run_playbook(playbook_name="manage_app_on_container.yml", tags=tags, limit=(host_names + [global_hdfs_data["namenode_host"]]), extravars=extravars)


def get_hdfs_transfer_time(task_timings):
    transfer_time = 0
    for task_name in ['Get input data', 'Put input data into target HDFS', 'Remove file in temporary location', 'Transfer data']:
        if task_name in task_timings: transfer_time += task_timings[task_name]
    return transfer_time

def download_global_hdfs_data_to_local(master_host, master_container, global_hdfs_data, containers_info):

    extravars = {
        "master_host": master_host,
        "master_container": master_container,
        "containers_info_str": containers_info
    }
    extravars.update(global_hdfs_data)

    _, task_timings = run_playbook(playbook_name="manage_app_on_container.yml", tags=["download_to_local"], limit=[global_hdfs_data['namenode_host']], extravars=extravars)

    return get_hdfs_transfer_time(task_timings)

def upload_local_hdfs_data_to_global(master_host, master_container, global_hdfs_data, containers_info):

    extravars = {
        "master_host": master_host,
        "master_container": master_container,
        "containers_info_str": containers_info
    }
    extravars.update(global_hdfs_data)

    _, task_timings = run_playbook(playbook_name="manage_app_on_container.yml", tags=["upload_to_global"], limit=[global_hdfs_data['namenode_host']], extravars=extravars)
    run_playbook(playbook_name="manage_app_on_container.yml", tags=["remove_global_hdfs_connection"], extravars=extravars)

    return get_hdfs_transfer_time(task_timings)

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

def get_hdfs_block_locations(namenode_host, namenode_container_name, hdfs_path, datanode_names):

    extravars = {
        "namenode_host": namenode_host,
        "namenode_container_name": namenode_container_name,
        "hdfs_path": hdfs_path,
        "datanode_names": datanode_names
    }

    output, _ = run_playbook(playbook_name="manage_app_on_container.yml", tags=["get_hdfs_block_locations"], limit=[namenode_host], extravars=extravars)

    ## Access to block locations (as datanode addresses) and the resolution of datanode names to addresses
    blocks_output = output.get("Get HDFS block locations_stdout", "")
    resolutions_output = output.get("Resolve HDFS datanode addresses_stdout", "")
    return blocks_output, resolutions_output
