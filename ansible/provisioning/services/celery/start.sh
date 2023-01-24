#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

cd $scriptDir/../serverless_containers_web

celery -A serverless_containers_web worker -l INFO -f $scriptDir/celery.log
