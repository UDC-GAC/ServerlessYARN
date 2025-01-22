#!/usr/bin/env bash

if [ -z "${1}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> rules file"
  exit 0
fi

RULES_FILE=${1}
source "${SC_INSTALLATION_PATH}/set_pythonpath.sh"

python3 "${RULES_FILE}"
