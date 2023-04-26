#!/bin/bash
set -e
HOST_NAMES=$1
APP_NAME=$2
CONTAINERS_INFO=$3
RM_HOST=$4
RM_CONTAINER=$5
VCORES=$6
MIN_VCORES=$7
SCHEDULER_MAXIMUM_MEMORY=$8
SCHEDULER_MINIMUM_MEMORY=$9
NODEMANAGER_MEMORY=${10}
MAP_MEMORY=${11}
MAP_MEMORY_JAVA_OPTS=${12}
REDUCE_MEMORY=${13}
REDUCE_MEMORY_JAVA_OPTS=${14}
MAPREDUCE_AM_MEMORY=${15}
MAPREDUCE_AM_MEMORY_JAVA_OPTS=${16}

cd ../../
INVENTORY=../ansible.inventory

unbuffer ansible-playbook manage_app_on_container.yml -i $INVENTORY -t setup_network,setup_hadoop -l $HOST_NAMES \
    --extra-vars \
        "containers_info_str=$CONTAINERS_INFO \
        rm_host=$RM_HOST \
        rm_container=$RM_CONTAINER \
        app_name=$APP_NAME \
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
        mapreduce_am_memory_java_opts=$MAPREDUCE_AM_MEMORY_JAVA_OPTS"
