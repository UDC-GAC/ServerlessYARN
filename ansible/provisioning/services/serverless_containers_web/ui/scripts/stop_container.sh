#!/bin/bash
set -e
HOST_NAME=$1
CONT_NAME=$2

#scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

cd ../../
INVENTORY=../ansible.inventory
CONFIG_FILE=config/config.yml

container_engine=`yq '.container_engine' < $CONFIG_FILE`
cgroups_version=`yq '.cgroups_version' < $CONFIG_FILE`

if [ $container_engine = "lxc" ]
then
    unbuffer ansible $HOST_NAME -i $INVENTORY -m shell -a "lxc stop $CONT_NAME"

elif [ $container_engine = "apptainer" ]
then
    if [ $cgroups_version = "v1" ]
    then
        unbuffer ansible $HOST_NAME -i $INVENTORY -m shell -a "sudo singularity instance stop $CONT_NAME"
    else
        unbuffer ansible $HOST_NAME -i $INVENTORY -m shell -a "singularity instance stop $CONT_NAME"
    fi

else
    echo "Error: No valid container engine"
    exit 1
fi
