#!/usr/bin/env bash

#########################################################################################################
# SAMPLE EXPERIMENT COMPÀRING DIFFERENT POWER-CAPPING METHODS UNDER AN INITIAL CPU ALLOCATION
#########################################################################################################
# Set initial CPU allocation
change_initial_allocation "${CPU_CURRENT_VALUES[${INITIAL_CPU_ALLOCATION}]}"
echo "Running tests with initial CPU allocation ${INITIAL_CPU_ALLOCATION}"

#########################################################################################################
# empirical-value: Run app with ServerlessContainers using a constant ratio determined experimentally
#########################################################################################################
mkdir -p "${RESULTS_DIR}/empirical-value"
register_logs_position

curl_wrapper bash "${SC_SCRIPTS_DIR}/change-shares-per-watt.sh" "${EMPIRICAL_SHARES_PER_WATT}"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
run_app "${APP_NAME}" "empirical-value"

save_logs "empirical-value"

#########################################################################################################
# tdp-value: Run app with ServerlessContainers using a constant ratio calculated according to TDP
#########################################################################################################
mkdir -p "${RESULTS_DIR}/tdp-value"
register_logs_position

curl_wrapper bash "${SC_SCRIPTS_DIR}/change-shares-per-watt.sh" "${TDP_SHARES_PER_WATT}"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
run_app "${APP_NAME}" "tdp-value"

save_logs "tdp-value"

#########################################################################################################
# ppe-proportional: Run app with ServerlessContainers using CPU/energy proportional rescaling
#########################################################################################################
mkdir -p "${RESULTS_DIR}/ppe-proportional"
register_logs_position

curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "proportional"
run_app "${APP_NAME}" "ppe-proportional"

save_logs "ppe-proportional"

#########################################################################################################
# model-boosted: Run app with ServerlessContainers using power modelling
#########################################################################################################
mkdir -p "${RESULTS_DIR}/model-boosted"
register_logs_position

curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model-reliability.sh" "low"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "modelling"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
run_app "${APP_NAME}" "model-boosted"

save_logs "model-boosted"

#########################################################################################################
# model-boosted-mr: Run app with ServerlessContainers using power modelling with medium reliability
#########################################################################################################
mkdir -p "${RESULTS_DIR}/model-boosted-mr"
register_logs_position

curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model-reliability.sh" "medium"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "modelling"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
run_app "${APP_NAME}" "model-boosted-mr"

save_logs "model-boosted-mr"

#########################################################################################################
# model-boosted-hr: Run app with ServerlessContainers using power modelling with high reliability
#########################################################################################################
mkdir -p "${RESULTS_DIR}/model-boosted-hr"
register_logs_position

curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model-reliability.sh" "high"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "modelling"
curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
run_app "${APP_NAME}" "model-boosted-hr"

save_logs "model-boosted-hr"

sleep 30

#########################################################################################################
# PROFILE EXPERIMENTS
#########################################################################################################
bash "${PROFILER_PATH}" "${APP_NAME}" "${RESULTS_DIR}" "${PLOTS_CONFIG_FILE}" "0"