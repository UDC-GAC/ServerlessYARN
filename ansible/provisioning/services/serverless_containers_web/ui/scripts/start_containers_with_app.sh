#!/bin/bash
set -e
HOST_NAMES=$1
CONTAINERS_INFO=$2
APP_DIR=$3
INSTALL_SCRIPT=$4
APP_JAR=$5
APP_TYPE=$6

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -t start_containers -l $HOST_NAMES,localhost \
    --extra-vars \
        "host_list=$HOST_NAMES \
        containers_info_str=$CONTAINERS_INFO \
        app_dir=$APP_DIR \
        install_script=$INSTALL_SCRIPT \
        app_jar=$APP_JAR \
        app_type=$APP_TYPE"

unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t start_containers \
    --extra-vars \
        "host_list=$HOST_NAMES \
        containers_info_str=$CONTAINERS_INFO"
