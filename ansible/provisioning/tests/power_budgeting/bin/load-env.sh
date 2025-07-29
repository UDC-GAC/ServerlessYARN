#!/usr/bin/env bash

BASE_DIR=$(dirname $(dirname -- "$(readlink -f -- "$BASH_SOURCE")"))

# General directories
export BIN_DIR="${BASE_DIR}/bin"
export CONF_DIR="${BASE_DIR}/etc"
export OUTPUT_DIR="${BASE_DIR}/out"
export CONF_APPS_DIR="${CONF_DIR}/apps"
export CONF_RULES_DIR="${CONF_DIR}/rules"
export CONF_SETUP_DIR="${CONF_DIR}/setup"
export CONF_ENTRYPOINT_DIR="${CONF_DIR}/entrypoint"
export CONF_PLOTS_DIR="${CONF_DIR}/plots"

# Management scripts
export SC_SCRIPTS_DIR="${BIN_DIR}/serverless_containers"
export APP_MNG_DIR="${BIN_DIR}/app_management"
export EXPERIMENTS_DIR="${BIN_DIR}/experiments"
export PROFILER_PATH="${BIN_DIR}/profiler/profile.sh"

# Configuration files
export CONFIG_FILE="${CONF_DIR}/experiments.json"

# ServerlessYARN and ServerlessContainers environment
export TEST_DIR=$(dirname "${BASE_DIR}")
export PROVISIONING_DIR=$(dirname "${TEST_DIR}")
export ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
export ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"
export SC_YARN_PATH="${HOME}/ServerlessYARN_install"
export SC_INSTALLATION_PATH="${SC_YARN_PATH}/ServerlessContainers"