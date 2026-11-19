## Helpers to sort, filter and look up structures (hosts, containers, apps) already retrieved from the StateDatabase
import re
import os
import functools

from django.conf import settings


def compareStructureNames(structure1, structure2):
    # When using a dict to store container info
    if isinstance(structure1, dict):
        cname1 = structure1['name']
        cname2 = structure2['name']
    # When using a tuple to store container info (host core mapping case))
    elif isinstance(structure1, tuple):
        cname1 = structure1[0]
        cname2 = structure2[0]
    # When using containers as strings
    else:
        cname1 = structure1
        cname2 = structure2

    id1 = re.sub('.*?([0-9]*)$',r'\1',cname1)
    id2 = re.sub('.*?([0-9]*)$',r'\1',cname2)

    if id1 != "" and id2 != "":
        basename1 = cname1[:-len(id1)]
        basename2 = cname2[:-len(id2)]
    else:
        basename1 = cname1
        basename2 = cname2

    if basename1 < basename2:
        return -1
    elif basename1 > basename2:
        return 1
    else:
        if id1 != "" and id2 != "":
            if int(id1) < int(id2):
                return -1
            elif int(id1) > int(id2):
                return 1
            else:
                return 0
        else:
            return 0


def getHostsNames(data):
    hosts = []
    for item in data:
        if item['subtype'] == 'host':
            hosts.append(item)

    hosts = sorted(hosts, key=functools.cmp_to_key(compareStructureNames))
    return hosts


def retrieve_app(apps, app_name):
    found_app = None

    for app in apps:
        if app['name'] == app_name:
            found_app = app
            break

    return found_app


def retrieve_global_hdfs_app(apps):
    namenode_container_info = None
    datanodes = []
    global_hdfs_app = retrieve_app(apps, settings.VARS_CONFIG['global_hdfs_app_name'])

    if global_hdfs_app:
        for container in global_hdfs_app['containers_full']:
            if 'namenode' in container['name']:
                namenode_container_info = container
            elif 'datanode' in container['name']:
                datanodes.append(container)

    return global_hdfs_app, namenode_container_info, datanodes


def getAppInfo(data, app_name):
    app = {}
    for item in data:
        if item['subtype'] == 'application' and item['name'] == app_name:
            return item

    return app


def getContainersFromApp(data, app):
    return [item for item in data if item['subtype'] == 'container' and item['name'] in app['containers']]


def getAppFiles(app):
    return {
        'runtime_files': os.path.basename(app['runtime_files']),
        'output_dir': os.path.basename(app['output_dir']),
        'install_script': os.path.basename(app['install_script']),
        'start_script': os.path.basename(app['start_script']),
        'stop_script': os.path.basename(app['stop_script']),
        'app_dir': os.path.dirname(app['start_script'])
    }
