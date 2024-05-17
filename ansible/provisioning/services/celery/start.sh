#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

cd $scriptDir/../serverless_containers_web

celery -A serverless_containers_web worker -Ofair -P gevent -l INFO -f $scriptDir/celery_`date +%d-%m-%y`.log
