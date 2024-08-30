#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${SCRIPT_DIR}/get-env.sh"
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export ORCHESTRATOR_PATH="${SERVERLESS_PATH}/scripts/orchestrator"

echo "DeActivating Guardian"
bash ${ORCHESTRATOR_PATH}/Guardian/deactivate.sh

echo "DeActivating Scaler"
bash ${ORCHESTRATOR_PATH}/Scaler/deactivate.sh
