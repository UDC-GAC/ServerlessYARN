## Big Data (Hadoop / Spark / HDFS) specific steps when adding and starting apps (check ui/views/apps/operations.py)

import yaml

from django.conf import settings

from ui.utils import DEFAULT_LIMIT_VALUES, DEFAULT_RESOURCE_VALUES
from ui.domain.structures import retrieve_global_hdfs_app

from serverlessyarn_utils.manage_inventory import AnsibleYamlInventory


## Add app
def set_bigdata_app_files(post_data, app_files):
    """Set the framework of Hadoop apps, which may change the app type (e.g., to 'spark_app') to build the corresponding container image"""
    if app_files["app_type"] == "hadoop_app":
        if post_data.get("add_extra_framework", False) and "framework" in post_data:
            ## An extra framework has been selected (e.g., Spark), we change the app_type to build the corresponding container image
            app_files["framework"] = post_data["framework"]
            if app_files["framework"] == "spark": app_files["app_type"] = "spark_app"
        else:
            ## If no extra framework has been selected, we select Hadoop to differentiate hadoop apps when retrieving them later from the StateDB
            app_files["framework"] = "hadoop"


## Start app
def add_global_hdfs_allocation_exclusions(allocation_exclusions):
    """Exclude the server disk used for global HDFS frontend data transfers from container allocation"""
    if settings.PLATFORM_CONFIG['global_hdfs'] and settings.PLATFORM_CONFIG['server_as_host']:
        server_name = AnsibleYamlInventory().get_server_hostname()
        allocation_exclusions[server_name] = {}
        allocation_exclusions[server_name]["disks"] = []
        allocation_exclusions[server_name]["disks"].append(settings.PLATFORM_CONFIG['global_hdfs_disk_name'])

def reserve_master_container_resources(app_resources):
    """
    Load the resources of the master container (ResourceManager/NameNode) and subtract them from the app resources,
    so the remaining app resources are distributed among the worker containers.
    """
    master_resources_config_file = str(settings.BASE_DIR) + "/../../apps/base/hadoop_app/master_config.yml"
    with open(master_resources_config_file, "r") as f: master_container_resources = yaml.load(f, Loader=yaml.FullLoader)

    app_resources['cpu']['max'] -= master_container_resources['cpu']['max']
    app_resources['cpu']['min'] -= master_container_resources['cpu']['min']
    app_resources['mem']['max'] -= master_container_resources['mem']['max']
    app_resources['mem']['min'] -= master_container_resources['mem']['min']
    if settings.PLATFORM_CONFIG['power_budgeting']:
        app_resources['energy']['max'] -= master_container_resources['energy']['max']
        app_resources['energy']['min'] -= master_container_resources['energy']['min']

    ## Load default values
    for resource in master_container_resources:
        res = master_container_resources[resource]
        if res["weight"]        == "default": res["weight"]        = DEFAULT_RESOURCE_VALUES['weight']
        if res["boundary"]      == "default": res["boundary"]      = DEFAULT_LIMIT_VALUES['boundary']
        if res["boundary_type"] == "default": res["boundary_type"] = DEFAULT_LIMIT_VALUES["boundary_type"]

    return master_container_resources

def set_master_container_resources(container_resources, master_container_resources):
    """Add the master container (ResourceManager/NameNode) resources to the containers to create"""
    container_resources['master'] = {}
    for resource in ["cpu", "mem"]:
        for key in master_container_resources[resource]:
            container_resources['master'][f"{resource}_{key}"] = master_container_resources[resource][key]
    if settings.PLATFORM_CONFIG['power_budgeting']:
        for key in master_container_resources["energy"]:
            container_resources['master'][f"energy_{key}"] = master_container_resources["energy"][key]

def check_data_locality_policy(assignation_policy, is_hadoop_app):
    """Return an error message if the 'Data-locality' allocation policy is requested but not available for the app"""
    if assignation_policy == "Data-locality" and not (is_hadoop_app and settings.PLATFORM_CONFIG['global_hdfs']):
        return "Data-locality allocation policy is only available for Hadoop apps when the global HDFS is enabled"
    return ""

def get_global_hdfs_data(post_data, apps, assignation_policy, assignation_requirements):
    """
    Get the info required by Hadoop apps to exchange data with the global HDFS (NameNode, DataNodes and data to read/write).
    If the 'Data-locality' allocation policy is used, the info to locate the data the app will read is added to 'assignation_requirements'.
    Returns the global HDFS data and an error message (empty if no error).
    """

    ## Currently this block of code will return an error when running a Hadoop app if the global HDFS is enabled but not running

    global_hdfs_data = {}
    ## Add global Namenode
    global_hdfs_app, namenode_container, datanodes = retrieve_global_hdfs_app(apps)
    for datanode in datanodes:
        datanode.pop('resources_form', None)
        datanode.pop('resources_form_helper', None)
        datanode.pop('limits_form', None)

    if not global_hdfs_app:
        return None, "Global HDFS requested but not found"
    if not namenode_container:
        return None, "Namenode not found in global HDFS"
    global_hdfs_data['namenode_container_name'] = namenode_container['name']
    global_hdfs_data['namenode_host'] = namenode_container['host']
    global_hdfs_data['number_of_datanodes'] = len(datanodes)
    global_hdfs_data['datanodes_info_str'] = str(datanodes).replace(' ', '')

    ## Get additional info (read/write data from/to hdfs)
    for condition, additional_info in [('read_from_global', ['global_input', 'local_output']),
                                        ('write_to_global', ['local_input', 'global_output'])]:
        if post_data.get(condition, False):
            for info in additional_info:
                global_hdfs_data[info] = post_data.get(info)

    ## Info required to locate the data that the app will read from global HDFS
    if assignation_policy == "Data-locality":
        assignation_requirements['data_locality'] = {
            'namenode_host': namenode_container['host'],
            'namenode_container_name': namenode_container['name'],
            'datanodes': {datanode['name']: datanode['host'] for datanode in datanodes},
            'global_input': global_hdfs_data.get('global_input', "")
        }

    return global_hdfs_data, ""
