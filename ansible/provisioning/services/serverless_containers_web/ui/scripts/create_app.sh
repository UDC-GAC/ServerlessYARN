#!/bin/bash
set -e
DEFINITION_FILE=$1
IMAGE_FILE=$2
APP_NAME=$3
FILES_DIR=$4
INSTALL_SCRIPT=$5

cd ../../
INVENTORY=../ansible.inventory

ansible-playbook start_containers_playbook.yml -i $INVENTORY -t create_app --extra-vars "template_definition_file=app_container.def definition_file=$DEFINITION_FILE image_file=$IMAGE_FILE app_name=$APP_NAME files_dir=$FILES_DIR install_script=$INSTALL_SCRIPT"
