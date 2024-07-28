#!/bin/bash
set -e

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
PROVISIONING_DIR=$(dirname "${SCRIPT_DIR}")
ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"

unbuffer ansible-playbook ${SCRIPT_DIR}/run_smusket.yml -i ${ANSIBLE_INVENTORY} -t setup_network,setup_ssh,setup_spark
