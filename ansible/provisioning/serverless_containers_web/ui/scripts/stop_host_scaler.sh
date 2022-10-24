#!/bin/bash

HOST_NAME=$1

cd ../
INVENTORY=../ansible.inventory

ansible-playbook stop_node_scaler_playbook.yml -i $INVENTORY -l $HOST_NAME