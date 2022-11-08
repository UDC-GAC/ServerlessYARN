#!/bin/bash

HOST_NAME=$1

cd ../../
INVENTORY=../ansible.inventory

ansible-playbook install_playbook.yml -i $INVENTORY -l $HOST_NAME
ansible-playbook start_containers_playbook.yml -i $INVENTORY -l $HOST_NAME,localhost
ansible-playbook launch_playbook.yml -i $INVENTORY -t start_containers