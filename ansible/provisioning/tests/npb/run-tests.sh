#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
BIN_DIR="${SCRIPT_DIR}/bin"
CONF_DIR="${SCRIPT_DIR}/etc"
OUTPUT_DIR="${SCRIPT_DIR}/out"
IMG_DIR="${SCRIPT_DIR}/img"
TEST_DIR=$(dirname "${SCRIPT_DIR}")
PROVISIONING_DIR=$(dirname "${TEST_DIR}")
ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"

CONTAINER_HOST="compute-2-2"
CONTAINER_NAME="compute-2-2-cont0"
DYNAMIC_SHARES_PER_WATT=28 # cpu_max_shares / (max_energy - min_energy)
STATIC_POWER_MODEL="polyreg_Single_Core"
DYNAMIC_POWER_MODEL="sgdregressor_Single_Core"


function log_timestamp() {
  local EXPERIMENT_NAME="${1}"
  local LABEL="${2}"
  echo "${EXPERIMENT_NAME} ${LABEL} $(date -u "+%Y-%m-%d %H:%M:%S%z")" | tee -a "${OUTPUT_DIR}/experiments.log"
}

function run_npb() {
  local EXPERIMENT_NAME="${1}"
  sleep 20
  log_timestamp "${EXPERIMENT_NAME}" "start"
  unbuffer ansible-playbook ${BIN_DIR}/run_npb.yml -i ${ANSIBLE_INVENTORY} -t start_app
  log_timestamp "${EXPERIMENT_NAME}" "stop"
  sleep 60
  bash "${BIN_DIR}/reset-container-limits.sh" "${CONTAINER_NAME}" "${CONTAINER_HOST}"
  sleep 60
}

# Create output and images directories
echo "Output directory: ${OUTPUT_DIR}"
echo "Images directory: ${IMG_DIR}"
mkdir -p "${OUTPUT_DIR}" "${IMG_DIR}"

#echo "Using ${CONF_DIR}/config.yml to set ServerlessYARN configuration"
#cp "${CONF_DIR}/config.yml" "${PROVISIONING_DIR}/config/config.yml"

#echo "Running ServerlessYARN"
#bash "${PROVISIONING_DIR}/scripts/start_all.sh"
#sleep 600

echo "Stopping Rebooter before tests"
bash "${BIN_DIR}/stop-rebooter.sh"

echo "Start and deactivate WattTrainer"
bash "${BIN_DIR}/start-watt-trainer.sh"
bash "${BIN_DIR}/deactivate-watt-trainer.sh"

echo "Running NPB tests"
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
bash "${BIN_DIR}/deactivate-modelling.sh"
run_npb "serverless_fixed_value"

#########################################################################################################
# serverless_dynamic_value: Run NPB with ServerlessContainers using a custom shares per watt value
#########################################################################################################
bash "${BIN_DIR}/change-shares-per-watt.sh" "${DYNAMIC_SHARES_PER_WATT}"
run_npb "serverless_dynamic_value"

#########################################################################################################
# serverless_static_model: Run NPB with ServerlessContainers using power modelling
#########################################################################################################
bash "${BIN_DIR}/activate-modelling.sh"
bash "${BIN_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
run_npb "serverless_static_model"

#########################################################################################################
# serverless_dynamic_model: Run NPB with ServerlessContainers using power modelling and online learning
#########################################################################################################
bash "${BIN_DIR}/activate-watt-trainer.sh"
bash "${BIN_DIR}/change-model.sh" "${DYNAMIC_POWER_MODEL}"
bash "${BIN_DIR}/reset-guardian.sh"
run_npb "serverless_dynamic_model"

sleep 30
python3 "${BIN_DIR}/get_metrics_opentsdb.py" "${OUTPUT_DIR}/experiments.log" "${IMG_DIR}"