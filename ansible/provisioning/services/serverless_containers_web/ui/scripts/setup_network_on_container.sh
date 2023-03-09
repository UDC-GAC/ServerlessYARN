#!/bin/bash
set -e
HOST_NAMES=$1
APP_CONTAINERS=$2

cd ../../
INVENTORY=../ansible.inventory

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t setup_network -l $HOST_NAMES \
    --extra-vars \
        "app_containers=$APP_CONTAINERS"
