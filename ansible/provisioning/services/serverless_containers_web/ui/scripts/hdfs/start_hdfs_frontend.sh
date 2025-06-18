#!/bin/bash
set -e
HOST_NAMES=$1
APP_TYPE=$2
CONTAINERS_INFO=$3
NN_HOST=$4
NN_CONTAINER=$5

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/../access_playbooks_dir.sh

unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -t setup_hdfs -l $HOST_NAMES \
    --extra-vars \
        "containers_info_str=$CONTAINERS_INFO \
        app_type=$APP_TYPE \
        nn_host=$NN_HOST \
        nn_container=$NN_CONTAINER"