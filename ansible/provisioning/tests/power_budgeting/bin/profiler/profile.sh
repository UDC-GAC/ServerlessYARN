#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

if [ -z "${2}" ]; then
  echo "At least 2 arguments are needed"
  echo "1 -> Application name (e.g., npb_1cont_1thread)"
  echo "2 -> Directory to read experiments info and store results (e.g., ./out)"
  echo "3 -> JSON file with plot configuration (Optional)"
  echo "4 -> Dynamic power budgeting, set 1 to process dynamic PBs (Optional)"
  exit 0
fi

APP_NAME="${1}"
RESULTS_DIR="${2}"
PLOT_CONFIG_FILE=""
DYN_PBS="0"

if [ -n "${3}" ]; then
  PLOT_CONFIG_FILE="${3}"
fi

if [ -n "${4}" ]; then
  DYN_PBS="${4}"
fi

# Add profiler path to PYTHONPATH
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

# Run profiler
python3 "${SCRIPT_DIR}/ExperimentsProfiler.py" "${APP_NAME}" "${RESULTS_DIR}" "${PLOT_CONFIG_FILE}" "${DYN_PBS}"
