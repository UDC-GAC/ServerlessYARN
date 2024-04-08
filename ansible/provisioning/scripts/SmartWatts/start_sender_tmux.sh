#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

if [ -z "${1}" ]
then
      echo "1 argument is needed"
      echo "1 -> SmartWatts output directory"
      exit 1
fi

SMARTWATTS_OUTPUT=$1
COMMAND="python3 ${scriptDir}/send_power_opentsdb.py ${SMARTWATTS_OUTPUT}"
echo "${COMMAND}"

tmux new -d -s "smartwatts_sender" "${COMMAND}"