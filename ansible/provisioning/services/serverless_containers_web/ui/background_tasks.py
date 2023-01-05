import time
import subprocess
import requests
from ui.update_inventory_file import add_containers_to_hosts,remove_container_from_host, add_host, remove_host

from celery import shared_task
from bs4 import BeautifulSoup
import redis
import json

# TODO: check if lock is actually working
lock = redis.Redis().lock("celery")

@shared_task
def start_containers_task(host, new_containers):

    # update inventory file
    with lock:
        add_containers_to_hosts(new_containers)

    rc = subprocess.Popen(["./ui/scripts/start_containers.sh",host], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = rc.communicate()

    if rc.returncode != 0:
        error = "Error starting containers {0}: {1}".format(str(new_containers),err.decode("utf-8"))
        raise Exception(error)

@shared_task
def add_host_task(host,cpu,mem,new_containers):

    # update_inventory_file
    with lock:
        add_host(structure_name,cpu,mem,new_containers)

    rc = subprocess.Popen(["./ui/scripts/configure_host.sh",host], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = rc.communicate()

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

            if rc.returncode != 0:
                error = "Error creating app {0}: {1}".format(app, err.decode("utf-8"))
                raise Exception(error)

    else:
        raise Exception(error)

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

        if rc.returncode != 0:
            error = "Error starting app {0} on container {1}: {2}".format(app, container, err.decode("utf-8"))
            raise Exception(error)
    else:
        raise Exception(error)

@shared_task
def start_containers_with_app_task(url, headers, host, new_containers, app, app_files):

    # update inventory file
    with lock:
        added_containers = add_containers_to_hosts({host: new_containers})

    # Start containers
    if app_files['install_script']:
        template_definition_file="app_container.def"
        definition_file = "{0}_container.def".format(app.replace(" ", "_"))
        image_file = "{0}_container.sif".format(app.replace(" ", "_"))
    else:
        template_definition_file="ubuntu_container.def"
        definition_file = "ubuntu_container.def"
        image_file = "ubuntu_container.sif"

    rc = subprocess.Popen(["./ui/scripts/start_containers_with_app.sh", host, app, template_definition_file, definition_file, image_file, app_files['files_dir'], app_files['install_script']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = rc.communicate()

    if rc.returncode != 0:
        error = "Error starting containers {0}: {1}".format(str(new_containers),err.decode("utf-8"))
        raise Exception(error)

    # Start app on containers
    for container in added_containers[host]:
        full_url = url + "container/{0}/{1}".format(container,app)
        add_container_to_app_task(full_url, headers, host, container, app, app_files)
        # Workaround to keep all updates to State DB
        time.sleep(0.25)

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

        if rc.returncode != 0:
            error = "Error stopping app {0} on container {1}: {2}".format(app, container, err.decode("utf-8"))
            raise Exception(error)

        if install_script != "":
            # remove container if it has been created specifically for this app
            # full_url[:full_url.rfind('/')] removes the last part of url -> .../container/host0-cont0/app1 -> .../container/host0-cont0
            remove_container_task(full_url[:full_url.rfind('/')], headers, host, container)

    else:
        raise Exception(error)