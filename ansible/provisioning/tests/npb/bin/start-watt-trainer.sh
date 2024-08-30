#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${SCRIPT_DIR}/get-env.sh"
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export SERVICES_PATH="${SERVERLESS_PATH}/scripts/services"

echo "Starting WattTrainer"
bash ${SERVICES_PATH}/watt_trainer/start_tmux.sh