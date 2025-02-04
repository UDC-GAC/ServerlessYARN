#!/usr/bin/env bash

if [ -z "${2}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> Application (e.g. npb, hadoop,...)"
  echo "2 -> Experiment (e.g. 1cont_1thread, 1cont32threads,...)"
  exit 0
fi

APP="${1}"
EXPERIMENT="${2}"

# Import auxiliar functions
. "${BIN_DIR}/functions.sh"

#########################################################################################################
# APPLICATION AND CONFIGURATION
#########################################################################################################
# Experiment
export EXPERIMENT_NAME=$(echo "${EXPERIMENT}" | jq -r '.name')
export DYNAMIC_POWER_BUDGETS=$(echo "${EXPERIMENT}" | jq -r '.dynamic_power_budgets')
export NUM_CONTAINERS=$(echo "${EXPERIMENT}" | jq -r '.params.num_containers')
export ASSIGNATION_POLICY=$(echo "${EXPERIMENT}" | jq -r '.params.assignation_policy')
export NUM_THREADS=$(echo "${EXPERIMENT}" | jq -r '.params.num_threads')
export NPB_KERNEL=$(echo "${EXPERIMENT}" | jq -r '.params.npb_kernel')
export DYNAMIC_SHARES_PER_WATT=$(echo "${EXPERIMENT}" | jq -r '.params.dynamic_shares_per_watt')
export STATIC_POWER_MODEL=$(echo "${EXPERIMENT}" | jq -r '.params.static_model')
export DYNAMIC_POWER_MODEL=$(echo "${EXPERIMENT}" | jq -r '.params.dynamic_model')
export HW_AWARE_POWER_MODEL=$(echo "${EXPERIMENT}" | jq -r '.params.hw_aware_model')

# App
export APP_RULES_FILENAME=$(echo "${EXPERIMENT}" | jq -r '.rules_file')
export APP_RULES_FILE="${APPS_RULES_DIR}/${APP}/${APP_RULES_FILENAME}"
export APP_CONFIG_FILENAME=$(echo "${EXPERIMENT}" | jq -r '.config_file')
export APP_CONFIG_FILE="${APPS_CONFIG_DIR}/${APP}/${APP_CONFIG_FILENAME}"
export APP_DIR=$(jq -r ".apps[] | select(.app == \"${APP}\") | .app_dir" "${CONFIG_FILE}")
export APP_NAME="${APP}_${EXPERIMENT_NAME}"
export BASE_RESULTS_DIR="${OUTPUT_DIR}/results_${APP_NAME}"


#########################################################################################################
# INITIALIZATION
#########################################################################################################
print_env

# Manage different configurations across different types of apps
manage_app_details

# Set application configuration
cp "${APP_CONFIG_FILE}" "${PROVISIONING_DIR}/apps/${APP_DIR}/app_config.yml"

# Set specific rules for this app
bash "${SC_MNG_DIR}/overwrite-rules.sh" "${APP_RULES_FILE}"

# Add application if it doesn't exists
add_app "${APP_DIR}"

echo "Ensure WattTrainer is deactivated"
curl_wrapper bash "${SC_MNG_DIR}/deactivate-service.sh" "WattTrainer"

echo "Ensure Rebalancer is deactivated"
curl_wrapper bash "${SC_MNG_DIR}/deactivate-service.sh" "Rebalancer"

#########################################################################################################
# EXPERIMENTS
#########################################################################################################
# Wait 2 minutes for cold start
sleep 120
echo "Running tests for app ${APP_NAME}"

# Run experiment without capping
. "${EXPERIMENTS_DIR}/no-capping.sh"

# Compare all the power capping methods initialising CPU limit at min, medium and max values
. "${EXPERIMENTS_DIR}/methods-comparison.sh"

# Test models and proportional scaling when changing power budget in real time
. "${EXPERIMENTS_DIR}/dynamic-power-budgeting.sh"


