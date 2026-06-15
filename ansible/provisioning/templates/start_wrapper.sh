#!/bin/bash

set -e

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

APP_NAME="{{ app_name }}"
CALLBACK_URL="http://${PLATFORM_SERVER_IP}:9000/ui/api/apps/stop/${APP_NAME}"

function notify_exit() {
  EXIT_CODE=$?
  curl -c "${SCRIPT_DIR}/cookies.txt" -s "http://${PLATFORM_SERVER_IP}:9000/ui/rules" > /dev/null
  CSRF_TOKEN=$(grep csrftoken "${SCRIPT_DIR}/cookies.txt" | awk '{print $7}')
  curl -X POST "${CALLBACK_URL}" -b "${SCRIPT_DIR}/cookies.txt" -H "X-CSRFToken: ${CSRF_TOKEN}"
  echo "Successfully notified exit"
  exit ${EXIT_CODE}
}

trap notify_exit EXIT

bash "${SCRIPT_DIR}/{{ start_script | basename }}"
