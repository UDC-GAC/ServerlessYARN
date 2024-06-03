#!/bin/bash
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "${BASH_SOURCE}")")

if [ -z "${3}" ]
then
      echo "2 arguments are needed"
      echo "1 -> Singularity command alias"
      echo "2 -> SmartWatts output directory"
      echo "3 -> Sampling frequency"
      exit 1
fi

SINGULARITY_COMMAND_ALIAS=${1}
SMARTWATTS_OUTPUT=${2}
SAMPLING_FREQUENCY=${3}

tmux new -d -s "power_sender" "bash ${SCRIPT_DIR}/start_power_sender.sh ${SINGULARITY_COMMAND_ALIAS} ${SMARTWATTS_OUTPUT} ${SAMPLING_FREQUENCY}"