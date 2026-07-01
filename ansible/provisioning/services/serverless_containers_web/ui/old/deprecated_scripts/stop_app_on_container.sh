#!/bin/bash
set -e
HOST_NAME=$1
CONTAINER=$2
APP_NAME=$3
APP_DIR=$4
FILES_DIR=$5
INSTALL_SCRIPT=$6
START_SCRIPT=$7
STOP_SCRIPT=$8
APP_JAR=$9
BIND_PATH=${10}
RM_CONTAINER=${11}

if [ -z "$BIND_PATH" ]
then
    BIND_PATH='{{ default_bind_path }}'
fi

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t stop_app -l $HOST_NAME \
    --extra-vars \
        "container=$CONTAINER \
        app_name=$APP_NAME \
        app_dir=$APP_DIR \
        files_dir=$FILES_DIR \
        install_script=$INSTALL_SCRIPT \
        start_script=$START_SCRIPT \
        stop_script=$STOP_SCRIPT \
        app_jar=$APP_JAR \
        bind_path=$BIND_PATH \
        rm_container=$RM_CONTAINER"
