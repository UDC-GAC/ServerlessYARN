#!/bin/bash
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "${BASH_SOURCE}")")
export PYTHONPATH=${SCRIPT_DIR}

if [ -z "${2}" ]
then
      echo "2 arguments are needed"
      echo "1 -> Installation path"
      echo "2 -> Sampling frequency"
      exit 1
fi

INSTALLATION_PATH=${1}
SAMPLING_FREQUENCY=${2}

python3 "${SCRIPT_DIR}"/src/PowerSender.py "${INSTALLATION_PATH}" "${SAMPLING_FREQUENCY}"