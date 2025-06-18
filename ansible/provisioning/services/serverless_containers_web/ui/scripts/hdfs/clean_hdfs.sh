#!/bin/bash
set -e
HOST=$1
CONTAINER=$2

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/../access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t clean_hdfs -l $HOST \
    --extra-vars \
        "container=$CONTAINER"
