#!/bin/bash
set -e
HOST_NAME=$1
CONT_NAME=$2

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh
CONFIG_FILE=config/config.yml

container_engine=$(grep 'container_engine' ${CONFIG_FILE} | awk '{print $2}' | tr -d '[:space:]' | tr -d '"')
singularity_command_alias=$(grep 'singularity_command_alias' ${CONFIG_FILE} | awk '{print $2}' | tr -d '[:space:]' | tr -d '"')
cgroups_version=$(grep 'cgroups_version' ${CONFIG_FILE} | awk '{print $2}' | tr -d '[:space:]' | tr -d '"')

if [ $container_engine = "lxc" ]
then
    unbuffer ansible $HOST_NAME -i $INVENTORY -m shell -a "lxc stop $CONT_NAME" || true ## workaround to avoid error even if container does not exist

elif [ $container_engine = "apptainer" ]
then
    if [ $cgroups_version = "v1" ]
    then
        unbuffer ansible $HOST_NAME -i $INVENTORY -m shell -a "sudo $singularity_command_alias instance stop $CONT_NAME" || true
    else
        #unbuffer ansible $HOST_NAME -i $INVENTORY -m shell -a "$singularity_command_alias instance stop $CONT_NAME"
        unbuffer ansible $HOST_NAME -i $INVENTORY -m shell -a "sudo $singularity_command_alias instance stop $CONT_NAME" || true
    fi

else
    echo "Error: No valid container engine"
    exit 1
fi
