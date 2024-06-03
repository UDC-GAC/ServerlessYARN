#!/bin/bash
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "${BASH_SOURCE}")")
export PYTHONPATH=${SCRIPT_DIR}

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

python3 "${SCRIPT_DIR}"/src/power_sender.py "${SINGULARITY_COMMAND_ALIAS}" "${SMARTWATTS_OUTPUT}" "${SAMPLING_FREQUENCY}"