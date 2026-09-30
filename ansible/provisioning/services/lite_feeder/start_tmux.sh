#!/usr/bin/env bash

export scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
tmux new -s "LITE_FEEDER" -d "bash $scriptDir/start.sh"
