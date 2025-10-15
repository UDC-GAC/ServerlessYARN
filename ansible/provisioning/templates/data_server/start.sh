#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
DATA_DIR="${SCRIPT_DIR}/data"

cd "${DATA_DIR}" && python3 -m http.server "{{ data_server_port }}"
