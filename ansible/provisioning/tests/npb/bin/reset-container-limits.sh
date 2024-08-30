#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
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
      "cpu": {"max": 3200,  "current": 3200,  "min": 100,   "guard": true},
      "mem": {"max": 204800, "current": 204800, "min": 512,  "guard": false},
      "energy": {"max": 150, "current": 150, "min": 10,  "guard": true}
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
      "cpu": {"boundary": 100},
      "mem": {"boundary": 256},
      "energy": {"boundary": 10}
    }
  }
}'