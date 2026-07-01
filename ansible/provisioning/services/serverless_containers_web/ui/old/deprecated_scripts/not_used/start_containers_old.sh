#!/bin/bash
set -e
HOST_NAME=$1
CONTAINERS=$2
MAX_CPU_PERCENTAGE_PER_CONTAINER=$3
MIN_CPU_PERCENTAGE_PER_CONTAINER=$4
CPU_BOUNDARY=$5
MAX_MEMORY_PER_CONTAINER=$6
MIN_MEMORY_PER_CONTAINER=$7
MEM_BOUNDARY=$8

cd ../../
INVENTORY=../ansible.inventory

unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -t start_containers -l $HOST_NAME,localhost \
    --extra-vars \
        "host_list=$HOST_NAME \
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