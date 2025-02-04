#!/usr/bin/env bash

. "${EXPERIMENTS_DIR}"/common.sh

#########################################################################################################
# BASELINE EXPERIMENT WITHOUT POWER CAPPING
#########################################################################################################

# Set CPU max as initial CPU limit
change_cpu_current_init_value "${CPU_CURRENT_VALUES[max]}"

# Set results directory for this experiments
RESULTS_DIR="${BASE_RESULTS_DIR}/no-capping"
mkdir -p "${RESULTS_DIR}"

#########################################################################################################
# no-capping: Run app without ServerlessContainers
#########################################################################################################
mkdir -p "${RESULTS_DIR}/no-capping"
register_logs_position

# Deactivate Serverless
curl_wrapper bash "${SC_MNG_DIR}/deactivate-service.sh" "Guardian"
curl_wrapper bash "${SC_MNG_DIR}/deactivate-service.sh" "Scaler"
run_app "${APP_NAME}" "no-capping"

save_logs "no-capping"

#########################################################################################################
# PLOT EXPERIMENTS
#########################################################################################################
python3 "${BIN_DIR}/plots/ExperimentsProfiler.py" "${APP_NAME}" "${OUTPUT_DIR}/experiments.log" "${OUTPUT_DIR}/containers" "${RESULTS_DIR}"
move_experiments_plot_info "no-capping"