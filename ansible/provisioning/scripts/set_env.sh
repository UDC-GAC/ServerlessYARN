#!/usr/bin/env bash

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
PROVISION_DIR=$( realpath ${scriptDir}/.. )
SCRIPTS_DIR=${PROVISION_DIR}/scripts
PLAYBOOK_DIR=${PROVISION_DIR}/playbooks

# Make sure the ansible.cfg file can be found, regardless of the directory
# from which this environment file is called
export ANSIBLE_CONFIG=${PROVISION_DIR}/ansible.cfg
ANSIBLE_INVENTORY=${PROVISION_DIR}/../ansible.inventory.yml

# The SSH connections of the playbooks have their ControlPath in ~/.ansible/cp,
# and Ansible only creates that directory when it chooses the ControlPath itself.
# This avoids SSH failures in new deployments ("unix_listener: cannot bind to path")
mkdir -p -m 700 "${HOME}/.ansible/cp"
