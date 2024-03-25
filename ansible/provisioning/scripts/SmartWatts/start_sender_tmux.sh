#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

if [ -z "${3}" ]
then
      echo "3 arguments are needed"
      echo "1 -> SmartWatts output directory"
      echo "2 -> SmartWatts targets"
      echo "3 -> Ansible configuration file path"
      exit 1
fi

SMARTWATTS_OUTPUT=$1
TARGETS=$2
CONFIG_PATH="${scriptDir}/../../${3}"
COMMAND="python3 ${scriptDir}/send_power_opentsdb.py ${SMARTWATTS_OUTPUT} ${TARGETS} ${CONFIG_PATH}"

tmux new -d -s "smartwatts_sender" "${COMMAND}"