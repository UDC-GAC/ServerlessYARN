#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

if [ -z "${2}" ]
then
      echo "2 arguments are needed"
      echo "1 -> Singularity command alias"
      echo "2 -> SmartWatts output directory"
      exit 1
fi

SINGULARITY_COMMAND_ALIAS=${1}
SMARTWATTS_OUTPUT=${2}
COMMAND="python3 ${scriptDir}/send_power_opentsdb.py ${SINGULARITY_COMMAND_ALIAS} ${SMARTWATTS_OUTPUT}"
echo "${COMMAND}"

tmux new -d -s "power_sender" "${COMMAND}"