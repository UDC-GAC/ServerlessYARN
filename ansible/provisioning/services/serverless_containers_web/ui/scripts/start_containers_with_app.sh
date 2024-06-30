#!/bin/bash
set -e
HOST_NAMES=$1
CONTAINERS_INFO=$2
APP_NAME=$3
TEMPLATE_DEFINITION_FILE=$4
DEFINITION_FILE=$5
IMAGE_FILE=$6
FILES_DIR=$7
INSTALL_SCRIPT=$8
APP_JAR=$9

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -t start_containers -l $HOST_NAMES,localhost \
    --extra-vars \
        "host_list=$HOST_NAMES \
        containers_info_str=$CONTAINERS_INFO \
        template_definition_file=$TEMPLATE_DEFINITION_FILE \
        definition_file=$DEFINITION_FILE \
        image_file=$IMAGE_FILE \
        app_name=$APP_NAME \
        files_dir=$FILES_DIR \
        install_script=$INSTALL_SCRIPT \
        app_jar=$APP_JAR"

unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t start_containers \
    --extra-vars \
        "host_list=$HOST_NAMES \
        containers_info_str=$CONTAINERS_INFO"
