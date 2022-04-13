#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
port=$1

python $scriptDir/manage.py runserver 0:$port
