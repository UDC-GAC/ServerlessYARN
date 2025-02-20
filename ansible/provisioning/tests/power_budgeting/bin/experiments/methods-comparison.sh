#!/usr/bin/env bash

. "${EXPERIMENTS_DIR}"/common.sh

# Activate Serverless
curl_wrapper bash "${SC_MNG_DIR}/activate-service.sh" "Guardian"
curl_wrapper bash "${SC_MNG_DIR}/activate-service.sh" "Scaler"

#########################################################################################################
# COMPARE POWER CAPPING METHODS
#########################################################################################################

# Test all the power capping methods with three initial CPU limits: min, medium and max
CPU_LIMITS=("min" "medium" "max")
for INITIAL_CPU_LIMIT in "${!CPU_LIMITS[@]}"; do
  CURRENT_INIT_VALUE="${CPU_CURRENT_VALUES[INITIAL_CPU_LIMIT]}"

  # Set results directory for this experiments
  RESULTS_DIR="${BASE_RESULTS_DIR}/${INITIAL_CPU_LIMIT}"
  mkdir -p "${RESULTS_DIR}"

  # Change initial CPU limit
  change_cpu_current_init_value "${CURRENT_INIT_VALUE}"
  echo "Running tests setting ${INITIAL_CPU_LIMIT} CPU as initial current CPU value (${CURRENT_INIT_VALUE})"

  #########################################################################################################
  # fixed-value: Run app with ServerlessContainers using a fixed shares per watt value
  #########################################################################################################
  mkdir -p "${RESULTS_DIR}/fixed-value"
  register_logs_position

  curl_wrapper bash "${SC_MNG_DIR}/change-shares-per-watt.sh" "5"
  curl_wrapper bash "${SC_MNG_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
  run_app "${APP_NAME}" "fixed-value"

  save_logs "fixed-value"

  #########################################################################################################
  # tdp-value: Run app with ServerlessContainers using a custom shares per watt value
  #########################################################################################################
  mkdir -p "${RESULTS_DIR}/tdp-value"
  register_logs_position

  curl_wrapper bash "${SC_MNG_DIR}/change-shares-per-watt.sh" "${DYNAMIC_SHARES_PER_WATT}"
  curl_wrapper bash "${SC_MNG_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
  run_app "${APP_NAME}" "tdp-value"

  save_logs "tdp-value"

  #########################################################################################################
  # ppe-proportional: Run app with ServerlessContainers using CPU/energy proportional rescaling
  #########################################################################################################
  mkdir -p "${RESULTS_DIR}/ppe-proportional"
  register_logs_position

  curl_wrapper bash "${SC_MNG_DIR}/change-energy-rules-policy.sh" "proportional"
  run_app "${APP_NAME}" "ppe-proportional"

  save_logs "ppe-proportional"

  #########################################################################################################
  # boosted-model: Run app with ServerlessContainers using power modelling
  #########################################################################################################
  mkdir -p "${RESULTS_DIR}/boosted-model"
  register_logs_position

  curl_wrapper bash "${SC_MNG_DIR}/change-model-reliability.sh" "low"
  curl_wrapper bash "${SC_MNG_DIR}/change-energy-rules-policy.sh" "modelling"
  curl_wrapper bash "${SC_MNG_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
  run_app "${APP_NAME}" "boosted-model"

  save_logs "boosted-model"

  #########################################################################################################
  # boosted-model-mr: Run app with ServerlessContainers using power modelling with medium reliability
  #########################################################################################################
  mkdir -p "${RESULTS_DIR}/boosted-model-mr"
  register_logs_position

  curl_wrapper bash "${SC_MNG_DIR}/change-model-reliability.sh" "medium"
  curl_wrapper bash "${SC_MNG_DIR}/change-energy-rules-policy.sh" "modelling"
  curl_wrapper bash "${SC_MNG_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
  run_app "${APP_NAME}" "boosted-model-mr"

  save_logs "boosted-model-mr"

  #########################################################################################################
  # boosted-model-hr: Run app with ServerlessContainers using power modelling with high reliability
  #########################################################################################################
  mkdir -p "${RESULTS_DIR}/boosted-model-hr"
  register_logs_position

  curl_wrapper bash "${SC_MNG_DIR}/change-model-reliability.sh" "high"
  curl_wrapper bash "${SC_MNG_DIR}/change-energy-rules-policy.sh" "modelling"
  curl_wrapper bash "${SC_MNG_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
  run_app "${APP_NAME}" "boosted-model-hr"

  save_logs "boosted-model-hr"

  sleep 30

  #########################################################################################################
  # PLOT EXPERIMENTS
  #########################################################################################################
  python3 "${BIN_DIR}/plots/ExperimentsProfiler.py" "${APP_NAME}" "${OUTPUT_DIR}/experiments.log" "${OUTPUT_DIR}/containers" "${RESULTS_DIR}"
  move_experiments_plot_info ""

done
