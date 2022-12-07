import time
import subprocess
import requests
from ui.update_inventory_file import add_containers_to_hosts,remove_container_from_host, add_host, remove_host

from celery import shared_task
from bs4 import BeautifulSoup
import redis

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
        error = "Error starting containers: {0}".format(err.decode("utf-8"))
        raise Exception(error)

@shared_task
def add_host_task(host,cpu,mem,new_containers):

    # update_inventory_file
    with lock:
        add_host(structure_name,cpu,mem,new_containers)

    rc = subprocess.Popen(["./ui/scripts/configure_host.sh",host], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = rc.communicate()

    if rc.returncode != 0:
        error = "Error adding host: {0}".format(err.decode("utf-8"))
        raise Exception(error)

@shared_task
def add_container_to_app_task(full_url, headers, host, container, app):

    r = requests.put(full_url, headers=headers)

    error = ""
    if (r != "" and r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error adding container " + container + "to app " + app + ": " + soup.get_text().strip()

    if (error == ""):
        ## TODO: start app on container (move files and execute script)
        pass
    else:
        raise Exception(error)

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
def remove_app_task(full_url, headers, app_name):

    r = requests.delete(full_url, headers=headers)
    
    error = ""
    if (r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error removing app " + app_name + ": " + soup.get_text().strip()

    ## TODO: actually stop app
    if (error == ""):
        pass
    else:
        raise Exception(error)

@shared_task
def remove_container_from_app_task(full_url, headers, container_name, app_name):

    r = requests.delete(full_url, headers=headers)

    error = ""
    if (r.status_code != requests.codes.ok):
        soup = BeautifulSoup(r.text, features="html.parser")
        error = "Error removing container " + container_name + " from app " + app_name + ": " + soup.get_text().strip()

    ## TODO: actually stop app
    if (error == ""):
        pass
    else:
        raise Exception(error)