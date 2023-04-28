#!/bin/bash
set -e
RM_HOST=$1
RM_CONTAINER=$2

cd ../../
INVENTORY=../ansible.inventory

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t stop_hadoop_cluster -l $RM_HOST \
    --extra-vars \
        "rm_host=$RM_HOST \
        rm_container=$RM_CONTAINER"
