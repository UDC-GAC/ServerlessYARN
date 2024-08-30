#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${SCRIPT_DIR}/get-env.sh"
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export SERVICES_PATH="${SERVERLESS_PATH}/scripts/services"

echo "Reset Guardian"
bash ${SERVICES_PATH}/guardian/stop.sh && bash ${SERVICES_PATH}/guardian/start_tmux.sh