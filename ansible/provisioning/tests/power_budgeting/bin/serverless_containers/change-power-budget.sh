#!/usr/bin/env bash

if [ -z "${2}" ]; then
  echo "At least 2 arguments are needed"
  echo "1 -> Application name"
  echo "2 -> Power budget (W)"
  exit 0
fi

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export ORCHESTRATOR_PATH="${SERVERLESS_PATH}/scripts/orchestrator"

bash "${ORCHESTRATOR_PATH}/Structures/set_structure_energy_max.sh" "${1}" "${2}"

