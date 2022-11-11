#!/bin/bash
set -e
HOST_NAME=$1

cd ../../
INVENTORY=../ansible.inventory

ansible-playbook stop_services_playbook.yml -i $INVENTORY -l $HOST_NAME -t stop_node_scaler