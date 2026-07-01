#!/bin/bash
set -e
HOST_NAME=$1

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook install_playbook.yml -i $INVENTORY -l $HOST_NAME
unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -l $HOST_NAME,localhost
unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t add_hosts,start_containers