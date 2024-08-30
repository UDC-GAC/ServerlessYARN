#!/bin/bash
set -e

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
TEST_DIR=$(dirname "${SCRIPT_DIR}")
PROVISIONING_DIR=$(dirname "${TEST_DIR}")
ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"

if [ -z "${1}" ];then
  echo "CAUTION: Smusket input not specified. Using default path: ~/ERR031558.fastq"
  unbuffer ansible-playbook ${SCRIPT_DIR}/run_smusket.yml -i ${ANSIBLE_INVENTORY} -t start_app
else
  unbuffer ansible-playbook ${SCRIPT_DIR}/run_smusket.yml -i ${ANSIBLE_INVENTORY} -t start_app \
      --extra-vars \
          "smusket_input=${1}"
fi