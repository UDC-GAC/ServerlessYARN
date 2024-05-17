#!/bin/bash
set -e
APP_JAR=$1
RM_HOST=$2
RM_CONTAINER=$3

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t set_hadoop_logs_timestamp -l $RM_HOST \
    --extra-vars \
        "app_jar=$APP_JAR \
        rm_container=$RM_CONTAINER"
