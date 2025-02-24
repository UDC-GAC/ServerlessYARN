#!/usr/bin/env bash

. "${EXPERIMENTS_DIR}"/common.sh

# Activate Serverless
curl_wrapper bash "${SC_SCRIPTS_DIR}/activate-service.sh" "Guardian"
curl_wrapper bash "${SC_SCRIPTS_DIR}/activate-service.sh" "Scaler"

#########################################################################################################
# DYNAMIC POWER BUDGETING: CHANGE POWER BUDGET IN REAL TIME
#########################################################################################################

# Set CPU min as initial CPU limit
change_cpu_current_init_value "${CPU_CURRENT_VALUES[min]}"

# Set results directory for this experiments
RESULTS_DIR="${BASE_RESULTS_DIR}/dynamic_power_budget"
mkdir -p "${RESULTS_DIR}"

#########################################################################################################
# ppe-proportional: Run app with ServerlessContainers using CPU/energy proportional rescaling
#########################################################################################################
mkdir -p "${RESULTS_DIR}/ppe-proportional"
register_logs_position

curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "proportional"
run_app_dynamic_pb "${APP_NAME}" "ppe-proportional" "${DYNAMIC_POWER_BUDGETS}"

save_logs "ppe-proportional"

#########################################################################################################
# boosted-model-hr: Run app with ServerlessContainers using power modelling with high reliability
#########################################################################################################
mkdir -p "${RESULTS_DIR}/boosted-model-hr"
register_logs_position

curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model-reliability.sh" "high"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "modelling"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
run_app_dynamic_pb "${APP_NAME}" "boosted-model-hr" "${DYNAMIC_POWER_BUDGETS}"

save_logs "boosted-model-hr"

#########################################################################################################
# PROFILE EXPERIMENTS
#########################################################################################################
bash "${PROFILER_PATH}" "${APP_NAME}" "${OUTPUT_DIR}/experiments.log" "${OUTPUT_DIR}/containers" "${RESULTS_DIR}" "dynamic_budgets"
move_experiments_plot_info ""