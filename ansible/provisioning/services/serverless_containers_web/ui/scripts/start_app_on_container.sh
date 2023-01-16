#!/bin/bash
set -e
HOST_NAME=$1
CONTAINER=$2
APP_NAME=$3
FILES_DIR=$4
INSTALL_SCRIPT=$5
START_SCRIPT=$6
STOP_SCRIPT=$7

cd ../../
INVENTORY=../ansible.inventory

ansible-playbook manage_app_on_container.yml -i $INVENTORY -t start_app -l $HOST_NAME \
    --extra-vars \
        "container=$CONTAINER \
        app_name=$APP_NAME \
        files_dir=$FILES_DIR \
        install_script=$INSTALL_SCRIPT \
        start_script=$START_SCRIPT \
        stop_script=$STOP_SCRIPT"
