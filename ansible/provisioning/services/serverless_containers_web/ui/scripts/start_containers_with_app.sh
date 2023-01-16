#!/bin/bash
set -e
HOST_NAME=$1
APP_NAME=$2
TEMPLATE_DEFINITION_FILE=$3
DEFINITION_FILE=$4
IMAGE_FILE=$5
FILES_DIR=$6
INSTALL_SCRIPT=$7

cd ../../
INVENTORY=../ansible.inventory

ansible-playbook start_containers_playbook.yml -i $INVENTORY -t start_containers -l $HOST_NAME,localhost \
    --extra-vars \
        "template_definition_file=$TEMPLATE_DEFINITION_FILE \
        definition_file=$DEFINITION_FILE \
        image_file=$IMAGE_FILE \
        app_name=$APP_NAME \
        files_dir=$FILES_DIR \
        install_script=$INSTALL_SCRIPT"

ansible-playbook launch_playbook.yml -i $INVENTORY -t start_containers
