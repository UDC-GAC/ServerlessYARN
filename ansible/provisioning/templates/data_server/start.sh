#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
DATA_DIR="${SCRIPT_DIR}/data"

cd "${DATA_DIR}"
echo "Serving the following files:"
ls -l | tr -s ' ' | cut -d" " -f 9
echo ""

python3 -m http.server "{{ data_server_port }}"