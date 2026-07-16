#!/usr/bin/env bash

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
PROVISION_DIR=$( realpath ${scriptDir}/.. )
SCRIPTS_DIR=${PROVISION_DIR}/scripts
PLAYBOOK_DIR=${PROVISION_DIR}/playbooks
ANSIBLE_CONFIG=${PROVISION_DIR}/ansible.cfg
ANSIBLE_INVENTORY=${PROVISION_DIR}/../ansible.inventory.yml
