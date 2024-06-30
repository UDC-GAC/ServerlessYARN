#!/bin/bash
set -e
HOST_NAME=$1

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook stop_services_playbook.yml -i $INVENTORY -l $HOST_NAME -t stop_node_scaler