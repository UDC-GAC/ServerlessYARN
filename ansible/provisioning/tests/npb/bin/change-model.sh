#!/usr/bin/env bash

if [ -z "${1}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> model name (e.g. polyreg_General)"
  exit 0
fi

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${SCRIPT_DIR}/get-env.sh"
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export ORCHESTRATOR_PATH="${SERVERLESS_PATH}/scripts/orchestrator"

echo "Changing model to ${1}"
bash ${ORCHESTRATOR_PATH}/Guardian/set_energy_model.sh "${1}"
