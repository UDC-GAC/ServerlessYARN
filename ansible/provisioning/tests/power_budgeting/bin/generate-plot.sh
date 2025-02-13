#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

if [ -z "${3}" ]; then
  echo "At least 2 arguments are needed"
  echo "1 -> Application name (e.g., npb_1cont_1thread)"
  echo "2 -> Experiment (e.g., min)"
  exit 1
fi

APP="${1}"
EXPERIMENT="${2}"
RESULTS_DIR="${SCRIPT_DIR}/../out/results_${APP}/${EXPERIMENT}"

python3 "${SCRIPT_DIR}/plots/ExperimentsProfiler.py" "${APP}" "${RESULTS_DIR}/experiments.log" "${RESULTS_DIR}/containers" "${RESULTS_DIR}"