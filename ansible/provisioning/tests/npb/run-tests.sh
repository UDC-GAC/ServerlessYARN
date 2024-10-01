#!/usr/bin/env bash

#########################################################################################################
# CHANGE EXPERIMENT HERE!!
#########################################################################################################
EXPERIMENT="1cont_1thread"

# Experiments configs
declare -A EXPERIMENT_CONFIG
EXPERIMENT_CONFIG["1cont_1thread"]="1,polyreg_Single_Core,sgdregressor_Single_Core,multisocket_hw_aware"
EXPERIMENT_CONFIG["1cont_32thread"]="32,polyreg_General,sgdregressor_General,multisocket_hw_aware"
EXPERIMENT_CONFIG["1cont_64thread"]="64,polyreg_General,sgdregressor_General,multisocket_hw_aware"

# Read config for current experiment
IFS="," read NPB_NUM_THREADS STATIC_POWER_MODEL DYNAMIC_POWER_MODEL HW_AWARE_POWER_MODEL <<< "${EXPERIMENT_CONFIG[${EXPERIMENT}]}"
DYNAMIC_SHARES_PER_WATT=28 # cpu_max_shares / (max_energy - min_energy)

# Directories
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
BIN_DIR="${SCRIPT_DIR}/bin"
CONF_DIR="${SCRIPT_DIR}/etc"
OUTPUT_DIR="${SCRIPT_DIR}/out"
IMG_DIR="${SCRIPT_DIR}/img"
TEST_DIR=$(dirname "${SCRIPT_DIR}")
PROVISIONING_DIR=$(dirname "${TEST_DIR}")
ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"

# Host information
IFS='.' read -ra HOST_INFO <<< $(hostname)
IFS='-' read -ra HOST_PARTS <<< "${HOST_INFO}"
REMOTE_HOST_NUM=$(( HOST_PARTS[2] + 1))
REMOTE_HOST="${HOST_PARTS[0]}-${HOST_PARTS[1]}-${REMOTE_HOST_NUM}"
CONTAINER_NAME="${REMOTE_HOST}-cont0"

function log_timestamp() {
  local EXPERIMENT_NAME="${1}"
  local LABEL="${2}"
  echo "${EXPERIMENT_NAME} ${LABEL} $(date -u "+%Y-%m-%d %H:%M:%S%z")" | tee -a "${OUTPUT_DIR}/experiments.log"
}

function run_npb() {
  local EXPERIMENT_NAME="${1}"
  sleep 20
  log_timestamp "${EXPERIMENT_NAME}" "start"
  unbuffer ansible-playbook ${BIN_DIR}/run_npb.yml -i ${ANSIBLE_INVENTORY} -t start_app --extra-vars "num_threads=${NPB_NUM_THREADS}"
  log_timestamp "${EXPERIMENT_NAME}" "stop"
  sleep 60
  bash "${BIN_DIR}/reset-container-limits.sh" "${CONTAINER_NAME}" "${REMOTE_HOST}"
  sleep 60
}

# Create output and images directories
echo "Output directory: ${OUTPUT_DIR}"
echo "Images directory: ${IMG_DIR}"
mkdir -p "${OUTPUT_DIR}" "${IMG_DIR}"

echo "Using ${CONF_DIR}/${EXPERIMENT}.yml to set ServerlessYARN configuration"
cp "${CONF_DIR}/${EXPERIMENT}.yml" "${CONF_DIR}/config.yml"
cp "${CONF_DIR}/config.yml" "${PROVISIONING_DIR}/config/config.yml"

echo "Running ServerlessYARN"
bash "${PROVISIONING_DIR}/scripts/start_all.sh"
sleep 600

echo "Stopping Rebooter before tests"
bash "${BIN_DIR}/stop-rebooter.sh"

echo "Start and deactivate WattTrainer"
bash "${BIN_DIR}/start-watt-trainer.sh"
bash "${BIN_DIR}/deactivate-watt-trainer.sh"

echo "Running NPB tests in ${CONTAINER_NAME}"
#########################################################################################################
# calibration: One execution first just to calibrate SmartWatts
#########################################################################################################
bash "${BIN_DIR}/deactivate-serverless.sh"
run_npb "calibration"

#########################################################################################################
# no_serverless: Run NPB without ServerlessContainers
#########################################################################################################
bash "${BIN_DIR}/deactivate-serverless.sh"
run_npb "no_serverless"

#########################################################################################################
# serverless_fixed_value: Run NPB with ServerlessContainers using a fixed shares per watt value
#########################################################################################################
bash "${BIN_DIR}/activate-serverless.sh"
bash "${BIN_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
run_npb "serverless_fixed_value"

#########################################################################################################
# serverless_dynamic_value: Run NPB with ServerlessContainers using a custom shares per watt value
#########################################################################################################
bash "${BIN_DIR}/change-shares-per-watt.sh" "${DYNAMIC_SHARES_PER_WATT}"
bash "${BIN_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
run_npb "serverless_dynamic_value"

#########################################################################################################
# proportional_scaling: Run NPB with ServerlessContainers using CPU/energy proportional rescaling
#########################################################################################################
bash "${BIN_DIR}/change-energy-rules-policy.sh" "proportional"
run_npb "proportional_scaling"

#########################################################################################################
# serverless_static_model: Run NPB with ServerlessContainers using power modelling
#########################################################################################################
bash "${BIN_DIR}/change-energy-rules-policy.sh" "modelling"
bash "${BIN_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
run_npb "serverless_static_model"

#########################################################################################################
# hw_aware_model: Run NPB with ServerlessContainers using HW aware power modelling
#########################################################################################################
bash "${BIN_DIR}/change-energy-rules-policy.sh" "modelling"
bash "${BIN_DIR}/change-model.sh" "${HW_AWARE_POWER_MODEL}"
run_npb "hw_aware_model"

#########################################################################################################
# serverless_dynamic_model: Run NPB with ServerlessContainers using power modelling and online learning
#########################################################################################################
bash "${BIN_DIR}/activate-watt-trainer.sh"
bash "${BIN_DIR}/change-energy-rules-policy.sh" "modelling"
bash "${BIN_DIR}/change-model.sh" "${DYNAMIC_POWER_MODEL}"
run_npb "serverless_dynamic_model"

sleep 30
python3 "${BIN_DIR}/get_metrics_opentsdb.py" "${OUTPUT_DIR}/experiments.log" "${IMG_DIR}" "${CONTAINER_NAME}"

sleep 259200
