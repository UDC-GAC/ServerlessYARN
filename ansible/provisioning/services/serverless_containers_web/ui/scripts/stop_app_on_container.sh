#!/bin/bash
set -e
HOST_NAME=$1
CONTAINER=$2
APP_NAME=$3
FILES_DIR=$4
INSTALL_SCRIPT=$5
START_SCRIPT=$6
STOP_SCRIPT=$7
APP_JAR=$8
BIND_PATH=$9

if [ -z "$BIND_PATH" ]
then
    BIND_PATH='{{ default_bind_path }}'
fi

cd ../../
INVENTORY=../ansible.inventory

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t stop_app -l $HOST_NAME \
    --extra-vars \
        "container=$CONTAINER \
        app_name=$APP_NAME \
        files_dir=$FILES_DIR \
        install_script=$INSTALL_SCRIPT \
        start_script=$START_SCRIPT \
        stop_script=$STOP_SCRIPT \
        app_jar=$APP_JAR \
        bind_path=$BIND_PATH"
