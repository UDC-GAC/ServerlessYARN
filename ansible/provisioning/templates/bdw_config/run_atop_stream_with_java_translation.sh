#!/usr/bin/env bash

## Script that YARN containers will run to report usage metrics + the disaggregated usage of each Java process

export PYTHONUNBUFFERED="yes"
export POST_DOC_BUFFER_TIMEOUT=5

METRIC="CPU,cpu,MEM,SWP,DSK,NET,PRC,PRM,PRD"
#METRIC="PRC,PRM,PRD"

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${scriptDir}/../../set_pythonpath.sh"

# Add PRN to support per-process network metrics using the netatop module if available

# If for any reason the module can't be used (e.g., containers of any sort are used), you
# can always use the nethogs script by installing it with the 'installation/install_nethgogs.sh' script
# and running it with the 'run_nethgogs.sh' script

# Uncomment this to run if netatop is used so that the module is loaded
# bash allow_netatop.sh

tmux new -s "ATOP" -d "atop 5 -a -P $METRIC \
    | python3 ${BDWATCHDOG_PATH}/MetricsFeeder/src/atop/atop_to_json_with_java_translation.py \
    | python3 ${BDWATCHDOG_PATH}/MetricsFeeder/src/pipelines/send_to_OpenTSDB.py"
