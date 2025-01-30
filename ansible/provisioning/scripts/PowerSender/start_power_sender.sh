#!/bin/bash
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "${BASH_SOURCE}")")
export PYTHONPATH=${SCRIPT_DIR}

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

python3 "${SCRIPT_DIR}"/src/PowerSender.py "${INSTALLATION_PATH}" "${POWER_METER}" "${SAMPLING_FREQUENCY}"