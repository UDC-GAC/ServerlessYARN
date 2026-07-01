#!/bin/bash
set -e
HOST_NAMES=$1
CONTAINERS_INFO=$2

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -t start_containers -l $HOST_NAMES,localhost \
    --extra-vars \
        "host_list=$HOST_NAMES \
        containers_info_str=$CONTAINERS_INFO"

unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t start_containers \
    --extra-vars \
        "host_list=$HOST_NAMES \
        containers_info_str=$CONTAINERS_INFO"