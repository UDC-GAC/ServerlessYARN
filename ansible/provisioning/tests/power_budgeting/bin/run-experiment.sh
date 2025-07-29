#!/usr/bin/env bash

if [ -z "${1}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> Experiment config in JSON format (e.g., '{\"include\":\"yes\",\"name\":\"npb_1cont_1thread-min\",...}'"
  exit 0
fi

EXPERIMENT_CONFIG="${1}"

#########################################################################################################
# ENVIRONMENT INITIALIZATION
#########################################################################################################
# Import auxiliar functions
. "${BIN_DIR}/functions.sh"

# Load common utilities for experiments
. "${EXPERIMENTS_DIR}"/common.sh

# Experiment configuration
export EXPERIMENT_NAME=$(echo ${EXPERIMENT_CONFIG} | jq -r '.name')
export RESULTS_DIR="${OUTPUT_DIR}/${EXPERIMENT_NAME}"
export RULES_FILE="${CONF_RULES_DIR}/$(echo ${EXPERIMENT_CONFIG} | jq -r '.rules_file')"
export SETUP_FILE="${CONF_SETUP_DIR}/$(echo ${EXPERIMENT_CONFIG} | jq -r '.setup_file')"
export ENTRYPOINT_FILE="${CONF_ENTRYPOINT_DIR}/$(echo ${EXPERIMENT_CONFIG} | jq -r '.entrypoint_file')"
export PLOTS_CONFIG_FILE="${CONF_RULES_DIR}/$(echo ${EXPERIMENT_CONFIG} | jq -r '.plots_config_file')"

# Application configuration
export APP_CONFIG_FILE="${CONF_APPS_DIR}/$(echo ${EXPERIMENT_CONFIG} | jq -r '.app_config')"
export APP_DIR=$(echo ${EXPERIMENT_CONFIG} | jq -r '.app_dir')
export APP_NAME=$(sed -nE 's/^names:[[:space:]]*"?([^"]*)"?/\1/p' "${APP_CONFIG_FILE}")

# Create directory to store experiment results
mkdir -p "${RESULTS_DIR}"

# Activate serverless control
curl_wrapper bash "${SC_SCRIPTS_DIR}/activate-service.sh" "Guardian"
curl_wrapper bash "${SC_SCRIPTS_DIR}/activate-service.sh" "Scaler"

# Deactivate WattTrainer and Rebalancer (comment this to use them)
curl_wrapper bash "${SC_SCRIPTS_DIR}/deactivate-service.sh" "WattTrainer"
curl_wrapper bash "${SC_SCRIPTS_DIR}/deactivate-service.sh" "Rebalancer"

#########################################################################################################
# APPLICATION INITIALIZATION
#########################################################################################################
# Set application configuration
cp "${APP_CONFIG_FILE}" "${PROVISIONING_DIR}/apps/${APP_DIR}/app_config.yml"

# Add application if it doesn't exists
add_app "${APP_DIR}"

# Set rules
bash "${SC_SCRIPTS_DIR}/overwrite-rules.sh" "${RULES_FILE}"

#########################################################################################################
# EXPERIMENT EXECUTION
#########################################################################################################
# Setup experiment environment
. "${SETUP_FILE}"

# Print environment
print_env

# Wait 2 minutes for cold start
sleep 120

# Run experiment
. "${ENTRYPOINT_FILE}"


