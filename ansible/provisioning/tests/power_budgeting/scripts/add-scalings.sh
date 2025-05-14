#!/usr/bin/env bash
#
# Script to run the profiler over multiple runs stored in TARGET_DIR and update the stats in TARGET_DIR
# Useful to update multiple experiments results at once when the data has changed
# Change TARGET_DIR with the name of the directory you want to use as a source
# TARGET_DIR tree should look like:
# - TARGET_DIR
#   - RUN_0
#     - results_<APP>
#       - <INITIAL-CPU>
#          - <METHOD-1>
#              ...
#          - <METHOD-N>
#   ...
#   - RUN_N

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
TESTS_DIR=$(dirname -- "${SCRIPT_DIR}")

if [ -z "${1}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> target directory (absolute path)"
fi

TARGET_DIR="${1}"
PROFILER_OUTPUT_DIR="${TESTS_DIR}/out"
PROFILER_DIR="${TESTS_DIR}/bin/profiler"

# MODIFY THIS TO INCLUDE OTHER EXPERIMENTS!!
CPU_VALUES=("min" "medium" "max")
APPS=("npb_1cont_1thread" "npb_1cont_32threads")

for i in $(seq 0 9); do
  RUN_DIR="${TARGET_DIR}/RUN_${i}"

  echo "Cleaning profiler directory"
  rm -rf "${PROFILER_OUTPUT_DIR}"/*

  echo "Copying run data from ${RUN_DIR} to profiler directory ${PROFILER_OUTPUT_DIR}"
  cp -r "${RUN_DIR}"/* "${PROFILER_OUTPUT_DIR}"

  for INITIAL_CPU in "${CPU_VALUES[@]}"; do
    for APP in "${APPS[@]}"; do

      EXPERIMENT_DIR="${PROFILER_OUTPUT_DIR}/results_${APP}/${INITIAL_CPU}"
      EXPERIMENTS_FILE="${EXPERIMENT_DIR}/experiments.log"
      CONTAINERS_FILE="${EXPERIMENT_DIR}/containers"
      STATS_FILE="${EXPERIMENT_DIR}/global_stats.md"

      echo "Running profiler to update experiment date for app ${APP} and ${INITIAL_CPU}: ${EXPERIMENT_DIR}"
      python3 "${PROFILER_DIR}/ExperimentsProfiler.py" "${APP}" "${EXPERIMENTS_FILE}" "${CONTAINERS_FILE}" "${EXPERIMENT_DIR}"

      DEST_DIR="${RUN_DIR}/results_${APP}/${INITIAL_CPU}/global_stats.md"

      echo "Updating stats from ${STATS_FILE} to ${DEST_DIR}"
      cp "${STATS_FILE}" "${DEST_DIR}"

    done
  done
done
