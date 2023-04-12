#!/bin/bash
set -e
HOST_NAME=$1
APP_NAME=$2
TEMPLATE_DEFINITION_FILE=$3
DEFINITION_FILE=$4
IMAGE_FILE=$5
FILES_DIR=$6
INSTALL_SCRIPT=$7
APP_JAR=$8
CONTAINERS=$9
MAX_CPU_PERCENTAGE_PER_CONTAINER=${10}
MIN_CPU_PERCENTAGE_PER_CONTAINER=${11}
CPU_BOUNDARY=${12}
MAX_MEMORY_PER_CONTAINER=${13}
MIN_MEMORY_PER_CONTAINER=${14}
MEM_BOUNDARY=${15}

cd ../../
INVENTORY=../ansible.inventory

unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -t start_containers -l $HOST_NAME,localhost \
    --extra-vars \
        "host_list=$HOST_NAME \
        template_definition_file=$TEMPLATE_DEFINITION_FILE \
        definition_file=$DEFINITION_FILE \
        image_file=$IMAGE_FILE \
        app_name=$APP_NAME \
        files_dir=$FILES_DIR \
        install_script=$INSTALL_SCRIPT \
        app_jar=$APP_JAR \
        container_list=$CONTAINERS \
        max_cpu_percentage_per_container=$MAX_CPU_PERCENTAGE_PER_CONTAINER \
        min_cpu_percentage_per_container=$MIN_CPU_PERCENTAGE_PER_CONTAINER \
        max_memory_per_container=$MAX_MEMORY_PER_CONTAINER \
        min_memory_per_container=$MIN_MEMORY_PER_CONTAINER"

unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t start_containers \
    --extra-vars \
        "host_list=$HOST_NAME \
        container_list=$CONTAINERS \
        max_cpu_percentage_per_container=$MAX_CPU_PERCENTAGE_PER_CONTAINER \
        min_cpu_percentage_per_container=$MIN_CPU_PERCENTAGE_PER_CONTAINER \
        cpu_boundary=$CPU_BOUNDARY \
        max_memory_per_container=$MAX_MEMORY_PER_CONTAINER \
        min_memory_per_container=$MIN_MEMORY_PER_CONTAINER \
        mem_boundary=$MEM_BOUNDARY"
