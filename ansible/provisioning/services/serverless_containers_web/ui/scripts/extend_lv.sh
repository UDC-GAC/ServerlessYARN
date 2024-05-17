#!/bin/bash
set -e
HOST_NAMES=$1
NEW_DISKS=$2
EXTRA_DISK=$3

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook install_playbook.yml -i $INVENTORY -t extend_lv -l $HOST_NAMES \
    --extra-vars \
        "new_disks_list=$NEW_DISKS \
        extra_disk=$EXTRA_DISK"

unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t extend_lv \
    --extra-vars \
        "host_list=$HOST_NAMES"
