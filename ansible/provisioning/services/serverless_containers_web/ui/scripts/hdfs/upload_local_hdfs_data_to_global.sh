#!/bin/bash
set -e
## Master container
RM_HOST=$1
RM_CONTAINER=$2
## Global HDFS info
GLOBAL_NAMENODE_CONTAINER=$3
LOCAL_INPUT=$4
GLOBAL_OUTPUT=$5

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/../access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t upload_to_global -l $RM_HOST \
    --extra-vars \
        "rm_host=$RM_HOST \
        rm_container=$RM_CONTAINER \
        global_namenode_container=$GLOBAL_NAMENODE_CONTAINER \
        local_input=$LOCAL_INPUT \
        global_output=$GLOBAL_OUTPUT"
