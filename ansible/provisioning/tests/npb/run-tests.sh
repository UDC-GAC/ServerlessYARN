#!/usr/bin/env bash

#########################################################################################################
# EXPERIMENTS
#########################################################################################################
# Current experiment
EXPERIMENT="1cont_1thread"

# TODO: Run all experiments in a loop -> App should be removed when a whole experiment finishes and another starts
# Experiments configs
declare -A EXPERIMENT_CONFIG
EXPERIMENT_CONFIG["1cont_1thread"]="1,polyreg_Single_Core,sgdregressor_Single_Core,multisocket_hw_aware"
EXPERIMENT_CONFIG["1cont_32thread"]="32,polyreg_General,sgdregressor_General,multisocket_hw_aware"
EXPERIMENT_CONFIG["1cont_64thread"]="64,polyreg_General,sgdregressor_General,multisocket_hw_aware"

#########################################################################################################
# ENVIRONMENT
#########################################################################################################
APP_NAME="npb_app"
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
BIN_DIR="${SCRIPT_DIR}/bin"
CONF_DIR="${SCRIPT_DIR}/etc"
OUTPUT_DIR="${SCRIPT_DIR}/out"
IMG_DIR="${SCRIPT_DIR}/img"
TEST_DIR=$(dirname "${SCRIPT_DIR}")
PROVISIONING_DIR=$(dirname "${TEST_DIR}")
ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"

#########################################################################################################
# AUXILIAR FUNCTIONS
#########################################################################################################
function log_timestamp() {
  local EXPERIMENT_NAME="${1}"
  local LABEL="${2}"
  echo "${EXPERIMENT_NAME} ${LABEL} $(date -u "+%Y-%m-%d %H:%M:%S%z")" | tee -a "${OUTPUT_DIR}/experiments.log"
}

function run_app() {
  local EXPERIMENT_NAME="${1}"
  sleep 20
  log_timestamp "${EXPERIMENT_NAME}" "start"
  python3 "${BIN_DIR}/run-app.py" "${APP_NAME}" "${OUTPUT_DIR}/containers"
  log_timestamp "${EXPERIMENT_NAME}" "stop"
  sleep 60
}

function change_npb_num_threads() {
  sed -i "s/^\(export NUM_THREADS=\)[0-9]\+$/\1${1}/" "${PROVISIONING_DIR}/apps/${APP_NAME}/files_dir/get_env.sh"
}

#########################################################################################################
# INITIALIZATION
#########################################################################################################
# Create output and images directories
echo "Output directory: ${OUTPUT_DIR}"
echo "Images directory: ${IMG_DIR}"
mkdir -p "${OUTPUT_DIR}" "${IMG_DIR}"

echo "Using ${CONF_DIR}/config.yml to set ServerlessYARN configuration"
cp "${CONF_DIR}/config.yml" "${PROVISIONING_DIR}/config/config.yml"

echo "Using ${CONF_DIR}/${EXPERIMENT}.yml to set NPB application configuration"
cp "${CONF_DIR}/${EXPERIMENT}.yml" "${PROVISIONING_DIR}/apps/${APP_NAME}/app_config.yml"

echo "Launch ServerlessYARN"
bash "${PROVISIONING_DIR}/scripts/start_all.sh"

echo "Ensure WattTrainer is deactivated"
bash "${BIN_DIR}/deactivate-watt-trainer.sh"

# Let the platform 5 minutes to stabilise
sleep 300

# Read config for current experiment
IFS="," read NPB_NUM_THREADS STATIC_POWER_MODEL DYNAMIC_POWER_MODEL HW_AWARE_POWER_MODEL <<< "${EXPERIMENT_CONFIG[${EXPERIMENT}]}"
DYNAMIC_SHARES_PER_WATT=28 # cpu_max_shares / (max_energy - min_energy)
change_npb_num_threads "${NPB_NUM_THREADS}"

echo "Running tests for app ${APP_NAME}"
#########################################################################################################
# calibration: One execution first just to calibrate SmartWatts
#########################################################################################################
bash "${BIN_DIR}/deactivate-serverless.sh"
run_app "calibration"

#########################################################################################################
# no_serverless: Run NPB without ServerlessContainers
#########################################################################################################
bash "${BIN_DIR}/deactivate-serverless.sh"
run_app "no_serverless"

#########################################################################################################
# serverless_fixed_value: Run NPB with ServerlessContainers using a fixed shares per watt value
#########################################################################################################
bash "${BIN_DIR}/activate-serverless.sh"
bash "${BIN_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
run_app "serverless_fixed_value"

#########################################################################################################
# serverless_dynamic_value: Run NPB with ServerlessContainers using a custom shares per watt value
#########################################################################################################
bash "${BIN_DIR}/change-shares-per-watt.sh" "${DYNAMIC_SHARES_PER_WATT}"
bash "${BIN_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
run_app "serverless_dynamic_value"

#########################################################################################################
# proportional_scaling: Run NPB with ServerlessContainers using CPU/energy proportional rescaling
#########################################################################################################
bash "${BIN_DIR}/change-energy-rules-policy.sh" "proportional"
run_app "proportional_scaling"

#########################################################################################################
# serverless_static_model: Run NPB with ServerlessContainers using power modelling
#########################################################################################################
bash "${BIN_DIR}/change-energy-rules-policy.sh" "modelling"
bash "${BIN_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
run_app "serverless_static_model"

#########################################################################################################
# hw_aware_model: Run NPB with ServerlessContainers using HW aware power modelling
#########################################################################################################
bash "${BIN_DIR}/change-energy-rules-policy.sh" "modelling"
bash "${BIN_DIR}/change-model.sh" "${HW_AWARE_POWER_MODEL}"
run_app "hw_aware_model"

#########################################################################################################
# serverless_dynamic_model: Run NPB with ServerlessContainers using power modelling and online learning
#########################################################################################################
bash "${BIN_DIR}/activate-watt-trainer.sh"
bash "${BIN_DIR}/change-energy-rules-policy.sh" "modelling"
bash "${BIN_DIR}/change-model.sh" "${DYNAMIC_POWER_MODEL}"
run_app "serverless_dynamic_model"

sleep 30
python3 "${BIN_DIR}/get-metrics-opentsdb.py" "${OUTPUT_DIR}/experiments.log" "${OUTPUT_DIR}/containers" "${IMG_DIR}"

# Keep SLURM job active just in case an error has occurred during execution
sleep 259200