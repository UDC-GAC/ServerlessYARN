#!/usr/bin/env bash

if [ -z "${1}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> model reliability (low or high)"
  exit 0
fi

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export ORCHESTRATOR_PATH="${SERVERLESS_PATH}/scripts/orchestrator"

echo "Changing model reliability to ${1}"
bash ${ORCHESTRATOR_PATH}/Guardian/set_energy_model_reliability.sh "${1}"
