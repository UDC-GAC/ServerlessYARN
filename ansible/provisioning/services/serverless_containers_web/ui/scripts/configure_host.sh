#!/bin/bash
set -e
HOST_NAME=$1

cd ../../
INVENTORY=../ansible.inventory

unbuffer ansible-playbook install_playbook.yml -i $INVENTORY -l $HOST_NAME
unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -l $HOST_NAME,localhost
unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t start_containers