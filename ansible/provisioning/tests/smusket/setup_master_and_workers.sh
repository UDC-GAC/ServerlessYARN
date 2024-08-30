#!/bin/bash
set -e

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
TEST_DIR=$(dirname "${SCRIPT_DIR}")
PROVISIONING_DIR=$(dirname "${TEST_DIR}")
ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"

if [ -z "${2}" ];then
  unbuffer ansible-playbook ${SCRIPT_DIR}/run_smusket.yml -i ${ANSIBLE_INVENTORY} -t setup_spark
else
  MASTER_HOST="${1}"
  MASTER_CONTAINER="${2}"
  unbuffer ansible-playbook ${SCRIPT_DIR}/run_smusket.yml -i ${ANSIBLE_INVENTORY} -t setup_spark \
      --extra-vars \
          "master_host=${MASTER_HOST} \
          master_container=${MASTER_CONTAINER}"
fi
