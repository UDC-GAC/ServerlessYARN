#!/bin/bash
set -e
HOST_NAME=$1

cd ../../
INVENTORY=../ansible.inventory

ansible-playbook start_containers_playbook.yml -i $INVENTORY -t start_containers -l $HOST_NAME,localhost
ansible-playbook launch_playbook.yml -i $INVENTORY -t start_containers