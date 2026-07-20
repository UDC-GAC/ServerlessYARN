#!/usr/bin/env bash
INTERVAL=5
export PYTHONUNBUFFERED="yes"
export POST_DOC_BUFFER_TIMEOUT=0.2
ENDPOINT_PATH="http://{{ opentsdb_url }}:{{ opentsdb_port }}"
export POST_ENDPOINT_PATH="${ENDPOINT_PATH}/api/put"
RETRY_INTERVAL=5

echo "Verifying OpenTSDB availability..."
while ! curl -s --head --request GET "${ENDPOINT_PATH}" | grep "200" > /dev/null; do
    echo "OpenTSDB is down. Retrying in ${RETRY_INTERVAL} seconds..."
    sleep ${RETRY_INTERVAL}
done

source "{{ bdwatchdog_source_path }}/set_pythonpath.sh"

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

python3 ${scriptDir}/DiskAtop.py --interval=$INTERVAL --cgroups_version="{{ cgroups_version }}" | python3 ${BDWATCHDOG_PATH}/MetricsFeeder/src/pipelines/send_to_OpenTSDB.py
