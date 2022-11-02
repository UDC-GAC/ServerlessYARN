#!/bin/bash

HOST_NAME=$1
CONT_NAME=$2

#scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

cd ../
INVENTORY=../ansible.inventory
CONFIG_FILE=config/config.yml

container_engine=`yq '.container_engine' < $CONFIG_FILE`

if [ $container_engine = "lxc"]
then
    ansible $HOST_NAME -i $INVENTORY -m shell -a "lxc stop $CONT_NAME"

elif [ $container_engine = "apptainer" ]
then
    ansible $HOST_NAME -i $INVENTORY -m shell -a "apptainer instance stop $CONT_NAME"

else
        echo "Error: No valid container engine"
        exit(1)
fi
