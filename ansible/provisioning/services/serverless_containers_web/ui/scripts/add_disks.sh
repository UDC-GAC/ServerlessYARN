#!/bin/bash
set -e
HOST_NAMES=$1
NEW_DISKS=$2

cd ../../
INVENTORY=../ansible.inventory

unbuffer ansible-playbook install_playbook.yml -i $INVENTORY -t add_disks -l $HOST_NAMES \
    --extra-vars \
        "new_disks_dict_str=$NEW_DISKS"

unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t add_disks \
    --extra-vars \
        "new_disks_dict_str=$NEW_DISKS"
