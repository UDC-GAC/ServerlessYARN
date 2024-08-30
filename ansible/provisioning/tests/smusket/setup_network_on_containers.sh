#!/bin/bash
set -e
#HOST_NAMES=$1
#CONTAINERS_INFO=$2

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
TEST_DIR=$(dirname "${SCRIPT_DIR}")
PROVISIONING_DIR=$(dirname "${TEST_DIR}")
ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"

unbuffer ansible-playbook ${SCRIPT_DIR}/run_smusket.yml -i ${ANSIBLE_INVENTORY} -t setup_network

