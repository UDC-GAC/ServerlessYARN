#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
port=$1

tmux new -d -s "web_interface" "bash $scriptDir/start.sh $port"

