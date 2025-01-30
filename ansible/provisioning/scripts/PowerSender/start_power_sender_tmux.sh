#!/bin/bash
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "${BASH_SOURCE}")")

if [ -z "${3}" ]
then
      echo "3 arguments are needed"
      echo "1 -> Installation path"
      echo "2 -> Power meter (e.g. rapl)"
      echo "3 -> Sampling frequency"
      exit 1
fi

INSTALLATION_PATH=${1}
POWER_METER=${2}
SAMPLING_FREQUENCY=${3}

tmux new -d -s "power_sender" "bash ${SCRIPT_DIR}/start_power_sender.sh ${INSTALLATION_PATH} ${POWER_METER} ${SAMPLING_FREQUENCY}"