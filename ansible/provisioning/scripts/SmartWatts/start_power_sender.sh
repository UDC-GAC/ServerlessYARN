#!/bin/bash
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "${BASH_SOURCE}")")
export PYTHONPATH=${SCRIPT_DIR}

if [ -z "$2" ]
then
      echo "2 arguments are needed"
      echo "1 -> Singularity command alias"
      echo "2 -> SmartWatts output directory"
      exit 1
fi
SINGULARITY_COMMAND_ALIAS=${1}
SMARTWATTS_OUTPUT=${2}

python3 "${SCRIPT_DIR}"/src/power_sender.py "${SINGULARITY_COMMAND_ALIAS}" "${SMARTWATTS_OUTPUT}"