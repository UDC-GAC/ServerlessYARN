#!/usr/bin/env bash
INTERVAL=5
export PYTHONUNBUFFERED="yes"
export POST_DOC_BUFFER_TIMEOUT=0.2
export POST_ENDPOINT_PATH="http://{{ opentsdb_url }}:{{ opentsdb_port }}/api/put"

source "{{ bdwatchdog_source_path }}/set_pythonpath.sh"

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

python3 ${scriptDir}/DiskAtop.py --interval=$INTERVAL --cgroups_version="{{ cgroups_version }}" | python3 ${BDWATCHDOG_PATH}/MetricsFeeder/src/pipelines/send_to_OpenTSDB.py
