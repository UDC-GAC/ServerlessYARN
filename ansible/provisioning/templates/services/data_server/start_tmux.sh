#!/usr/bin/env bash
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

tmux new -d -s "data_server" "bash ${SCRIPT_DIR}/start.sh"