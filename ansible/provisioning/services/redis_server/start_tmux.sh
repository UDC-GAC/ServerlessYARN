#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
installation_dir=$1

tmux new -d -s "redis_server" "bash $scriptDir/start.sh $installation_dir"