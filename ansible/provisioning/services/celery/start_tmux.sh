#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

tmux new -d -s "celery" "bash $scriptDir/start.sh"