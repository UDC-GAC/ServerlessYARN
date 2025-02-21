#!/bin/bash
set -e
HOST=$1
NAMENODE_CONTAINER=$2
DIR_TO_CREATE=$3

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/../access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t create_dir_on_hdfs -l $HOST \
    --extra-vars \
        "container=$NAMENODE_CONTAINER \
        dest_path=$DIR_TO_CREATE"
