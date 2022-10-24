#!/bin/bash

HOST_NAME=$1
CONT_NAME=$2

cd ../
INVENTORY=../ansible.inventory

ansible $HOST_NAME -i $INVENTORY -m shell -a "lxc stop $CONT_NAME"