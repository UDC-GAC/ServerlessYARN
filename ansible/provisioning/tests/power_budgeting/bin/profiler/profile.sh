#!/usr/bin/env bash

if [ -z "${4}" ]; then
  echo "At least 4 arguments are needed"
  echo "1 -> Application name (e.g., npb_1cont_1thread)"
  echo "2 -> Experiments log file (e.g., ./out/experiments.log)"
  echo "3 -> Containers log file (e.g., ./out/containers)"
  echo "4 -> Directory to store results and read experiments info (e.g., ./out)"
  exit 0
fi

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

# Add profiler path to PYTHONPATH
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

APP_NAME="${1}"
EXPERIMENTS_LOG_FILE="${2}"
CONTAINERS_LOG_FILE="${3}"
RESULTS_DIR="${4}"

if [ -n "${5}" ]; then
  # Dynamic power budgets paremeter is included
  python3 "${SCRIPT_DIR}/ExperimentsProfiler.py" "${APP_NAME}" "${EXPERIMENTS_LOG_FILE}" "${CONTAINERS_LOG_FILE}" "${RESULTS_DIR}" "${5}"
else
  python3 "${SCRIPT_DIR}/ExperimentsProfiler.py" "${APP_NAME}" "${EXPERIMENTS_LOG_FILE}" "${CONTAINERS_LOG_FILE}" "${RESULTS_DIR}"
fi