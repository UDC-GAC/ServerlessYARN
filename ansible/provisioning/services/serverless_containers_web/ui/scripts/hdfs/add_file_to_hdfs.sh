#!/bin/bash
set -e
HOST=$1
NAMENODE_CONTAINER=$2
FILE_TO_ADD=$3
DEST_PATH=$4

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/../access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t add_file_to_hdfs -l $HOST \
    --extra-vars \
        "namenode_container=$NAMENODE_CONTAINER \
        origin_path=$FILE_TO_ADD \
        dest_path=$DEST_PATH"
