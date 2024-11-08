#!/usr/bin/env bash

if [ -z "${1}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> CPU shares per watt (e.g. 5)"
  exit 0
fi

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export ORCHESTRATOR_PATH="${SERVERLESS_PATH}/scripts/orchestrator"

echo "Changing shares per watt to ${1}"
bash ${ORCHESTRATOR_PATH}/Guardian/set_cpu_shares_per_watt.sh "${1}"
