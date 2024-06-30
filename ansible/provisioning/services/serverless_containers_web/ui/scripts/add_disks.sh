#!/bin/bash
set -e
HOST_NAMES=$1
NEW_DISKS=$2

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook install_playbook.yml -i $INVENTORY -t add_disks -l $HOST_NAMES \
    --extra-vars \
        "new_disks_dict_str=$NEW_DISKS"

unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t add_disks \
    --extra-vars \
        "new_disks_dict_str=$NEW_DISKS"
