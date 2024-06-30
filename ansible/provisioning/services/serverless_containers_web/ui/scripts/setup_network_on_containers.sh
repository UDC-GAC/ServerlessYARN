#!/bin/bash
set -e
HOST_NAMES=$1
CONTAINERS_INFO=$2

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t setup_network -l $HOST_NAMES \
    --extra-vars \
        "containers_info_str=$CONTAINERS_INFO"
