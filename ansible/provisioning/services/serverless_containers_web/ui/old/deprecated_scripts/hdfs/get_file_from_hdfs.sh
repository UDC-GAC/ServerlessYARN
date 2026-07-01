#!/bin/bash
set -e
HOST=$1
NAMENODE_CONTAINER=$2
FILE_TO_DOWNLOAD=$3
DEST_PATH=$4

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/../access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t get_file_from_hdfs -l $HOST \
    --extra-vars \
        "namenode_container=$NAMENODE_CONTAINER \
        origin_path=$FILE_TO_DOWNLOAD \
        dest_path=$DEST_PATH"
