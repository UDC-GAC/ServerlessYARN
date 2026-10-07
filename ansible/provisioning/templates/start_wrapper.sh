#!/bin/bash

set -e

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

APP_NAME="{{ app_name }}"
CONTAINER_NAME="{{ container }}"
CALLBACK_URL="http://${PLATFORM_SERVER_IP}:9000/ui/api/apps/stop/${APP_NAME}"
APP_STARTED_URL="http://${PLATFORM_SERVER_IP}:{{ orchestrator_port | default(5000) }}/structure/${CONTAINER_NAME}/app_started"

function notify_start() {
  ## Notify the Orchestrator that the application starts in this container (only used by the EnergyManager).
  ## The application starts even if it fails
  if curl -s -f -m 10 -X PUT "${APP_STARTED_URL}" > /dev/null; then
    echo "Successfully notified start"
  else
    echo "Warning: the start could not be notified to the Orchestrator"
  fi
}

function notify_exit() {
  ## Get script exit code
  EXIT_CODE=$?

  ## Get script runtime
  START_TIME=$1
  END_TIME=`date +%s.%N`
  RUNTIME=$( echo "$END_TIME - $START_TIME" | bc -l )
  echo "Start script took ${RUNTIME} seconds"

  ## Get CSRF TOKEN
  curl -c "${SCRIPT_DIR}/cookies.txt" -s "http://${PLATFORM_SERVER_IP}:9000/ui/rules" > /dev/null
  CSRF_TOKEN=$(grep csrftoken "${SCRIPT_DIR}/cookies.txt" | awk '{print $7}')

  ## Send POST request back to server
  curl -X POST "${CALLBACK_URL}" -b "${SCRIPT_DIR}/cookies.txt" \
    -H "X-CSRFToken: ${CSRF_TOKEN}" \
    -H "X-Sender-Host: $(hostname)" \
    -d "runtime=$RUNTIME&exit_code=$EXIT_CODE"

  echo "Successfully notified exit"
  exit ${EXIT_CODE}
}

{% if scaling_service | default('scaler') == 'energy_manager' -%}
notify_start
{%- endif %}

start=`date +%s.%N`
trap 'notify_exit $start' EXIT

bash "${SCRIPT_DIR}/{{ start_script | basename }}"
