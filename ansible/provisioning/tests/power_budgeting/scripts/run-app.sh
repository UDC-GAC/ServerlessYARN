#!/usr/bin/env bash

if [ -z "${3}" ]; then
  echo "At least 3 arguments are needed"
  echo "1 -> App name (it must be registered in ServerlessYARN)"
  echo "2 -> App directory (e.g., npb_app, hadoop_app,...)"
  echo "3 -> Tests name"
  exit 0
fi
# e.g., bash scripts/run-app.sh npb_1cont_32threads user/npb_app my_tests
APP_NAME="${1}"
APP_DIR="${2}"
TESTS_NAME="${3}"

TESTS_DIR=$(dirname -- $(dirname -- "$(readlink -f -- "$BASH_SOURCE")"))

# Load testing environment
. "${TESTS_DIR}/bin/load-env.sh"

# Import auxiliar functions
. "${BIN_DIR}/functions.sh"

# Load common utilities for experiments execution
. "${EXPERIMENTS_DIR}"/common.sh

# Ensure output and result directories exist
export RESULTS_DIR="${OUTPUT_DIR}/${TESTS_NAME}"
mkdir -p "${RESULTS_DIR}"

pip install -r ${TESTS_DIR}/requirements.txt

print_env

#########################################################################################################
# EXPERIMENT EXECUTION EXAMPLE
#########################################################################################################
# Set experiment configuration
export EXPERIMENT_NAME="example"
export NUM_CONTAINERS=1
export ASSIGNATION_POLICY="Best-effort"

mkdir -p "${RESULTS_DIR}/${EXPERIMENT_NAME}"

# Change ServerlessContainers config as desired (e.g., Guardian or Scaler config)
# There are some useful script to do this in SC_SCRIPTS_DIR. Example of changing shares/W and rules-policy of Guardian:
#   curl_wrapper bash "${SC_SCRIPTS_DIR}/change-shares-per-watt.sh" "5"
#   curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "fixed-ratio"

# change_npb_kernel \"ft\"
# change_npb_num_threads 32
echo "Changing npb kernel and threads"
change_npb_kernel \"ft\"
change_npb_num_threads 4

# Register Guardian and Scaler logs position
echo "Register Guardian and Scaler logs position"
register_logs_position

# Run application in framework
echo "Run app trough web interface"
run_app "${APP_NAME}" "${EXPERIMENT_NAME}"

# Save Guardian and Scaler logs
echo "Save Guardian and Scaler logs"
save_logs "${EXPERIMENT_NAME}"

#########################################################################################################
# PROFILE EXPERIMENTS
#########################################################################################################
bash "${PROFILER_PATH}" "${APP_NAME}" "${RESULTS_DIR}"