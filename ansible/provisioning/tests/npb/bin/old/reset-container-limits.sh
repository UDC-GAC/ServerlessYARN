#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
CONFIG_FILE="$(dirname ${SCRIPT_DIR})/etc/config.yml"
source "${SCRIPT_DIR}/get-env.sh"
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"
export ORCHESTRATOR_PATH="${SERVERLESS_PATH}/scripts/orchestrator"
source "${ORCHESTRATOR_PATH}/set_env.sh"

if [ -z "${2}" ]; then
  echo "At least 2 arguments are needed"
  echo "1 -> container name (e.g., compute-2-2-cont0)"
  echo "2 -> host name (e.g., host0)"
  exit 0
fi

# Get current CPU and energy limits
CPU_MAX=$(grep 'max_cpu_percentage_per_container' "${CONFIG_FILE}" | cut -d ':' -f 2 | tr -d '[:space:]' | tr -d '"')
CPU_MIN=$(grep 'min_cpu_percentage_per_container' "${CONFIG_FILE}" | cut -d ':' -f 2 | tr -d '[:space:]' | tr -d '"')
CPU_BOUNDARY=$(grep 'cpu_boundary' "${CONFIG_FILE}" | cut -d ':' -f 2 | tr -d '[:space:]' | tr -d '"')
ENERGY_MAX=$(grep 'max_energy_per_container' "${CONFIG_FILE}" | cut -d ':' -f 2 | tr -d '[:space:]' | tr -d '"')
ENERGY_MIN=$(grep 'min_energy_per_container' "${CONFIG_FILE}" | cut -d ':' -f 2 | tr -d '[:space:]' | tr -d '"')
ENERGY_BOUNDARY=$(grep 'energy_boundary' "${CONFIG_FILE}" | cut -d ':' -f 2 | tr -d '[:space:]' | tr -d '"')

# Desubscribe container
curl -X DELETE -H "Content-Type: application/json" http://${ORCHESTRATOR_REST_URL}/structure/container/${1}

sleep 20

# Subscribe container
curl -X PUT -H "Content-Type: application/json" http://${ORCHESTRATOR_REST_URL}/structure/container/${1} -d \
'{
  "container":
  {
    "name": "'${1}'",
    "resources": {
      "cpu": {"max": '${CPU_MAX}',  "current": '${CPU_MAX}',  "min": '${CPU_MIN}', "guard": true},
      "mem": {"max": 204800, "current": 204800, "min": 512, "guard": false},
      "energy": {"max": '${ENERGY_MAX}', "current": '${ENERGY_MAX}', "min": '${ENERGY_MIN}', "guard": true}
    },
    "host_rescaler_ip": "'${2}'",
    "host_rescaler_port": "8000",
    "host": "'${2}'",
    "guard": true,
    "subtype": "container"
  },
  "limits":
  {
    "resources": {
      "cpu": {"boundary": '${CPU_BOUNDARY}'},
      "mem": {"boundary": 256},
      "energy": {"boundary": '${ENERGY_BOUNDARY}'}
    }
  }
}'