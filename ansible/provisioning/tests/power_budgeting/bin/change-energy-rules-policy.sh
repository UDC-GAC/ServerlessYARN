#!/usr/bin/env bash

if [ -z "${1}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> policy (e.g. modelling, proportional)"
  exit 0
fi

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export ORCHESTRATOR_PATH="${SERVERLESS_PATH}/scripts/orchestrator"

ENERGY_RULES=("EnergyRescaleUp" "EnergyRescaleDown")

echo "Change energy rules policy to ${1}"
for RULE in "${ENERGY_RULES[@]}"; do
  echo "${ORCHESTRATOR_PATH}/Rules/change_policy.sh ${RULE} ${1}"
  bash "${ORCHESTRATOR_PATH}/Rules/change_policy.sh" "${RULE}" "${1}"
done
