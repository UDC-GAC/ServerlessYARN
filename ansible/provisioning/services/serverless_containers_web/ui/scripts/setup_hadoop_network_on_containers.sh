#!/bin/bash
set -e
HOST_NAMES=$1
APP_NAME=$2
APP_TYPE=$3
CONTAINERS_INFO=$4
RM_HOST=$5
RM_CONTAINER=$6
VCORES=$7
MIN_VCORES=$8
SCHEDULER_MAXIMUM_MEMORY=$9
SCHEDULER_MINIMUM_MEMORY=${10}
NODEMANAGER_MEMORY=${11}
MAP_MEMORY=${12}
MAP_MEMORY_JAVA_OPTS=${13}
REDUCE_MEMORY=${14}
REDUCE_MEMORY_JAVA_OPTS=${15}
MAPREDUCE_AM_MEMORY=${16}
MAPREDUCE_AM_MEMORY_JAVA_OPTS=${17}
DATANODE_D_HEAPSIZE=${18}
NODEMANAGER_D_HEAPSIZE=${19}

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t setup_network,setup_hadoop -l $HOST_NAMES \
    --extra-vars \
        "containers_info_str=$CONTAINERS_INFO \
        rm_host=$RM_HOST \
        rm_container=$RM_CONTAINER \
        app_name=$APP_NAME \
        app_type=$APP_TYPE \
        vcores=$VCORES \
        min_vcores=$MIN_VCORES \
        scheduler_maximum_memory=$SCHEDULER_MAXIMUM_MEMORY \
        scheduler_minimum_memory=$SCHEDULER_MINIMUM_MEMORY \
        nodemanager_memory=$NODEMANAGER_MEMORY \
        map_memory=$MAP_MEMORY \
        map_memory_java_opts=$MAP_MEMORY_JAVA_OPTS \
        reduce_memory=$REDUCE_MEMORY \
        reduce_memory_java_opts=$REDUCE_MEMORY_JAVA_OPTS \
        mapreduce_am_memory=$MAPREDUCE_AM_MEMORY \
        mapreduce_am_memory_java_opts=$MAPREDUCE_AM_MEMORY_JAVA_OPTS \
        datanode_heapsize=$DATANODE_D_HEAPSIZE \
        nodemanager_heapsize=$NODEMANAGER_D_HEAPSIZE"
