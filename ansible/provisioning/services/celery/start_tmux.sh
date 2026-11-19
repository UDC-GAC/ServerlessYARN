#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
autoreload=${1:-false}

tmux new -d -s "celery" "bash $scriptDir/start.sh $autoreload"
