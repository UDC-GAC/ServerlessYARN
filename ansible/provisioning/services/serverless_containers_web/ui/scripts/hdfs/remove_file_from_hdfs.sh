#!/bin/bash
set -e
HOST=$1
NAMENODE_CONTAINER=$2
PATH_TO_REMOVE=$3

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/../access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t remove_file_from_hdfs -l $HOST \
    --extra-vars \
        "container=$NAMENODE_CONTAINER \
        dest_path=$PATH_TO_REMOVE"
