#!/usr/bin/env bash

if [ -z "${1}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> service (e.g. Guardian, Rebalancer)"
  exit 0
fi

SERVICE=${1}

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export ORCHESTRATOR_PATH="${SERVERLESS_PATH}/scripts/orchestrator"

echo "DeActivating ${SERVICE}"
bash ${ORCHESTRATOR_PATH}/${SERVICE}/deactivate.sh