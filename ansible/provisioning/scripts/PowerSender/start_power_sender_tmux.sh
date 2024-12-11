#!/bin/bash
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "${BASH_SOURCE}")")

if [ -z "${2}" ]
then
      echo "2 arguments are needed"
      echo "1 -> Installation path"
      echo "2 -> Sampling frequency"
      exit 1
fi

INSTALLATION_PATH=${1}
SAMPLING_FREQUENCY=${2}

tmux new -d -s "power_sender" "bash ${SCRIPT_DIR}/start_power_sender.sh ${INSTALLATION_PATH} ${SAMPLING_FREQUENCY}"