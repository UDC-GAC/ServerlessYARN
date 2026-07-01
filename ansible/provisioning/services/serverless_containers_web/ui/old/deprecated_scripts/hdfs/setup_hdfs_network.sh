#!/bin/bash
set -e
HOST_NAMES=$1
APP_NAME=$2
APP_TYPE=$3
CONTAINERS_INFO=$4
RM_HOST=$5
RM_CONTAINER=$6
DATANODE_D_HEAPSIZE=$7

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/../access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t setup_network,setup_hdfs -l $HOST_NAMES \
    --extra-vars \
        "containers_info_str=$CONTAINERS_INFO \
        rm_host=$RM_HOST \
        rm_container=$RM_CONTAINER \
        app_name=$APP_NAME \
        app_type=$APP_TYPE \
        datanode_heapsize=$DATANODE_D_HEAPSIZE"
