#!/usr/bin/env bash

if [ -z "${2}" ]; then
  echo "At least 1 argument is needed"
  echo "1 -> Application (e.g. npb, hadoop,...)"
  echo "2 -> Experiment (e.g. 1cont_1thread, 1cont32threads,...)"
  exit 0
fi

APP="${1}"
EXPERIMENT="${2}"

# Dictionary to save the position of the logs from some ServerlessContainers services
declare -A SC_LOGS_START=(
  ["guardian"]="0"
  ["scaler"]="0"
)

#########################################################################################################
# APPLICATION AND CONFIGURATION
#########################################################################################################
APP_NAME="${APP}_${EXPERIMENT}"
APP_DIR="${APP}_app"
RESULTS_DIR="${OUTPUT_DIR}/results_${APP}_${EXPERIMENT}"

if [ "${APP}" == "hadoop" ]; then
  APP_DIR="${APP}_sample"
fi

# Read config for current experiment
source "${CONF_DIR}/experiment-config.sh"
IFS="," read NUM_THREADS STATIC_POWER_MODEL DYNAMIC_POWER_MODEL HW_AWARE_POWER_MODEL <<< "${EXPERIMENT_CONFIG[${EXPERIMENT}]}"

#########################################################################################################
# AUXILIAR FUNCTIONS
#########################################################################################################
function print_env() {
  echo "ENVIRONMENT FOR APP ${APP} AND EXPERIMENT ${EXPERIMENT}"
  echo "EXPERIMENT: ${EXPERIMENT}"
  echo "APP_NAME: ${APP_NAME}"
  echo "APP_DIR: ${APP_DIR}"
  echo "APP_CONFIG_DIR: ${APP_CONFIG_DIR}"
  echo "NUM_THREADS: ${NUM_THREADS}"
  echo "STATIC_POWER_MODEL: ${STATIC_POWER_MODEL}"
  echo "DYNAMIC_POWER_MODEL: ${DYNAMIC_POWER_MODEL}"
  echo "HW_AWARE_POWER_MODEL: ${HW_AWARE_POWER_MODEL}"
  echo "BIN_DIR: ${BIN_DIR}"
  echo "CONF_DIR: ${CONF_DIR}"
  echo "RESULTS_DIR: ${RESULTS_DIR}"
  echo "TEST_DIR: ${TEST_DIR}"
  echo "PROVISIONING_DIR: ${PROVISIONING_DIR}"
  echo "ANSIBLE_DIR: ${ANSIBLE_DIR}"
  echo "ANSIBLE_INVENTORY: ${ANSIBLE_INVENTORY}"
}

function register_logs_position() {
  for SERVICE in "${!SC_LOGS_START[@]}"; do
    SC_LOGS_START[$SERVICE]=$(wc -l "${SC_INSTALLATION_PATH}/${SERVICE}.log" | awk '{print $1}')
  done
}

function save_logs() {
  for SERVICE in "${!SC_LOGS_START[@]}"; do
    sed -n "${SC_LOGS_START[$SERVICE]},\$p" "${SC_INSTALLATION_PATH}/${SERVICE}.log" > "${RESULTS_DIR}/${1}/${SERVICE}.log"
  done
}

function log_timestamp() {
  local EXPERIMENT_NAME="${1}"
  local LABEL="${2}"
  echo "${EXPERIMENT_NAME} ${LABEL} $(date -u "+%Y-%m-%d %H:%M:%S%z")" | tee -a "${OUTPUT_DIR}/experiments.log"
}

function run_app() {
  local APP_NAME="${1}"
  local EXPERIMENT_NAME="${2}"
  sleep 20
  log_timestamp "${EXPERIMENT_NAME}" "start"
  python3 "${BIN_DIR}/run-app.py" "${APP_NAME}" "${OUTPUT_DIR}/containers"
  log_timestamp "${EXPERIMENT_NAME}" "stop"
  sleep 60
}

function change_npb_num_threads() {
  sed -i "s/^\(export NUM_THREADS=\)[0-9]\+$/\1${1}/" "${PROVISIONING_DIR}/apps/${APP_DIR}/files_dir/get_env.sh"
}

function change_npb_kernel() {
  sed -i "s/^\(export NPB_KERNELS_TO_RUN=\)(.*)/\1(${1})/" "${PROVISIONING_DIR}/apps/${APP_DIR}/files_dir/get_env.sh"
}

#########################################################################################################
# INITIALIZATION
#########################################################################################################
print_env

# Create directory to store the results of the experiment
mkdir -p "${RESULTS_DIR}"

# Set application configuration
cp "${APP_CONFIG_DIR}/${EXPERIMENT}.yml" "${PROVISIONING_DIR}/apps/${APP_DIR}/app_config.yml"

# Add application if it doesn't exists
python3 "${BIN_DIR}/add-app.py" "${APP_DIR}"

# TODO: If more exceptions appears for each app, do this in a separated file
if [ "${APP}" == "npb" ]; then
  change_npb_num_threads "${NUM_THREADS}"
  change_npb_kernel '"ft"'
fi

echo "Ensure WattTrainer is deactivated"
bash "${BIN_DIR}/deactivate-watt-trainer.sh"

#########################################################################################################
# EXPERIMENTS
#########################################################################################################
# Wait 2 minutes for cold start
sleep 120

echo "Running tests for app ${APP_NAME}"
#########################################################################################################
# calibration: One execution first just to calibrate SmartWatts
#########################################################################################################
mkdir -p "${RESULTS_DIR}/calibration"
register_logs_position

bash "${BIN_DIR}/deactivate-serverless.sh"
run_app "${APP_NAME}" "calibration"
sleep 30

save_logs "calibration"

#########################################################################################################
# no_serverless: Run app without ServerlessContainers
#########################################################################################################
mkdir -p "${RESULTS_DIR}/no_serverless"
register_logs_position

bash "${BIN_DIR}/deactivate-serverless.sh"
run_app "${APP_NAME}" "no_serverless"

save_logs "no_serverless"

#########################################################################################################
# serverless_fixed_value: Run app with ServerlessContainers using a fixed shares per watt value
#########################################################################################################
mkdir -p "${RESULTS_DIR}/serverless_fixed_value"
register_logs_position

bash "${BIN_DIR}/activate-serverless.sh"
bash "${BIN_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
run_app "${APP_NAME}" "serverless_fixed_value"

save_logs "serverless_fixed_value"

#########################################################################################################
# serverless_dynamic_value: Run app with ServerlessContainers using a custom shares per watt value
#########################################################################################################
mkdir -p "${RESULTS_DIR}/serverless_dynamic_value"
register_logs_position

bash "${BIN_DIR}/change-shares-per-watt.sh" "${DYNAMIC_SHARES_PER_WATT}"
bash "${BIN_DIR}/change-energy-rules-policy.sh" "fixed-ratio"
run_app "${APP_NAME}" "serverless_dynamic_value"

save_logs "serverless_dynamic_value"

#########################################################################################################
# proportional_scaling: Run app with ServerlessContainers using CPU/energy proportional rescaling
#########################################################################################################
mkdir -p "${RESULTS_DIR}/proportional_scaling"
register_logs_position

bash "${BIN_DIR}/change-energy-rules-policy.sh" "proportional"
run_app "${APP_NAME}" "proportional_scaling"

save_logs "proportional_scaling"

#########################################################################################################
# serverless_static_model: Run app with ServerlessContainers using power modelling
#########################################################################################################
mkdir -p "${RESULTS_DIR}/serverless_static_model"
register_logs_position

bash "${BIN_DIR}/change-energy-rules-policy.sh" "modelling"
bash "${BIN_DIR}/change-model.sh" "${STATIC_POWER_MODEL}"
run_app "${APP_NAME}" "serverless_static_model"

save_logs "serverless_static_model"

#########################################################################################################
# hw_aware_model: Run app with ServerlessContainers using HW aware power modelling
#########################################################################################################
mkdir -p "${RESULTS_DIR}/hw_aware_model"
register_logs_position

bash "${BIN_DIR}/change-energy-rules-policy.sh" "modelling"
bash "${BIN_DIR}/change-model.sh" "${HW_AWARE_POWER_MODEL}"
run_app "${APP_NAME}" "hw_aware_model"

save_logs "hw_aware_model"

#########################################################################################################
# serverless_dynamic_model: Run app with ServerlessContainers using power modelling and online learning
#########################################################################################################
mkdir -p "${RESULTS_DIR}/serverless_dynamic_model"
register_logs_position

bash "${BIN_DIR}/activate-watt-trainer.sh"
bash "${BIN_DIR}/change-energy-rules-policy.sh" "modelling"
bash "${BIN_DIR}/change-model.sh" "${DYNAMIC_POWER_MODEL}"
run_app "${APP_NAME}" "serverless_dynamic_model"

save_logs "serverless_dynamic_model"

sleep 30

#########################################################################################################
# PLOT EXPERIMENTS
#########################################################################################################
pip3 install -r requirements.txt
python3 "${BIN_DIR}/get-metrics-opentsdb.py" "${APP_NAME}" "${OUTPUT_DIR}/experiments.log" "${OUTPUT_DIR}/containers" "${RESULTS_DIR}"
