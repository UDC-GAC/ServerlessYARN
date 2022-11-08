#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
port=$1

python3 $scriptDir/manage.py runserver 0:$port
