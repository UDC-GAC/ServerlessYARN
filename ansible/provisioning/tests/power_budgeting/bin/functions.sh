#!/usr/bin/env bash

function print_env() {
  echo "ENVIRONMENT FOR APP ${APP} AND EXPERIMENT ${EXPERIMENT_NAME}"
  echo "EXPERIMENT: ${EXPERIMENT_NAME}"
  echo "APP: ${APP}"
  echo "APP_NAME: ${APP_NAME}"
  echo "APP_DIR: ${APP_DIR}"
  echo "APP_RULES_FILE: ${APP_RULES_FILE}"
  echo "APP_CONFIG_FILE: ${APP_CONFIG_FILE}"
  echo "NUM_CONTAINERS: ${NUM_CONTAINERS}"
  echo "ASSIGNATION_POLICY: ${ASSIGNATION_POLICY}"
  echo "NUM_THREADS: ${NUM_THREADS}"
  echo "STATIC_POWER_MODEL: ${STATIC_POWER_MODEL}"
  echo "DYNAMIC_POWER_MODEL: ${DYNAMIC_POWER_MODEL}"
  echo "HW_AWARE_POWER_MODEL: ${HW_AWARE_POWER_MODEL}"
  echo "BIN_DIR: ${BIN_DIR}"
  echo "CONF_DIR: ${CONF_DIR}"
  echo "BASE_RESULTS_DIR: ${BASE_RESULTS_DIR}"
  echo "TEST_DIR: ${TEST_DIR}"
  echo "PROVISIONING_DIR: ${PROVISIONING_DIR}"
  echo "ANSIBLE_DIR: ${ANSIBLE_DIR}"
  echo "ANSIBLE_INVENTORY: ${ANSIBLE_INVENTORY}"
}

function change_npb_num_threads() {
  sed -i "s/^\(export NUM_THREADS=\)[0-9]\+$/\1${1}/" "${PROVISIONING_DIR}/apps/${APP_DIR}/files_dir/get_env.sh"
}

function change_npb_kernel() {
  sed -i "s/^\(export NPB_KERNELS_TO_RUN=\)(.*)/\1(${1})/" "${PROVISIONING_DIR}/apps/${APP_DIR}/files_dir/get_env.sh"
}

function manage_app_details() {
  # TODO: If more exceptions appears for each app, do this in a separated file
  if [ "${APP}" == "npb" ]; then
    if [ "${NUM_THREADS}" != "null" ]; then
      change_npb_num_threads "${NUM_THREADS}"
    fi
    if [ "${NPB_KERNEL}" != "null" ]; then
      change_npb_kernel \"${NPB_KERNEL}\"
    fi
  fi
}

function change_cpu_current_init_value() {
  # Change the CPU current value assigned by default in add_containers_API_v3.py
  sed -i "s/put_field_data\[.container.\]\[.resources.\]\[.cpu.\]\[.current.\] =.*/put_field_data[\"container\"][\"resources\"][\"cpu\"][\"current\"] = ${1}/" "${PROVISIONING_DIR}/scripts/stateDatabase/add_containers_API_v3.py"
}

function register_logs_position() {
  for SERVICE in "${!SC_LOGS_START[@]}"; do
    SC_LOGS_START[$SERVICE]=$(wc -l "${SC_INSTALLATION_PATH}/${SERVICE}.log" | awk '{print $1}')
  done
}

function move_experiments_plot_info() {
  cp "${OUTPUT_DIR}/experiments.log" "${RESULTS_DIR}/${1}/" && : > "${OUTPUT_DIR}/experiments.log"
  cp "${OUTPUT_DIR}/containers" "${RESULTS_DIR}/${1}/" && : > "${OUTPUT_DIR}/containers"
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

function curl_wrapper() {
  STATUS_CODE=$("$@" 2>&1 | grep -oE '^[0-9]{3}')
  echo "${@} ${STATUS_CODE}"
}

function add_app() {
  local APP_DIR="${1}"
  python3 "${APP_MNG_DIR}/add-app.py" "${PROVISIONING_DIR}" "${APP_DIR}"
}

function run_app() {
  local APP_NAME="${1}"
  local EXPERIMENT_NAME="${2}"
  sleep 20
  log_timestamp "${EXPERIMENT_NAME}" "start"
  python3 "${APP_MNG_DIR}/run-app.py" "${APP_NAME}" "${OUTPUT_DIR}/containers" "${RESULTS_DIR}/${EXPERIMENT_NAME}" "${NUM_CONTAINERS}" "${ASSIGNATION_POLICY}"
  log_timestamp "${EXPERIMENT_NAME}" "stop"
  sleep 60
}

function run_app_dynamic_pb() {
  local APP_NAME="${1}"
  local EXPERIMENT_NAME="${2}"
  local DYNAMIC_POWER_BUDGETS="${3}"
  sleep 20
  log_timestamp "${EXPERIMENT_NAME}" "start"
  python3 "${APP_MNG_DIR}/run-app.py" "${APP_NAME}" "${OUTPUT_DIR}/containers" "${RESULTS_DIR}/${EXPERIMENT_NAME}" \
                                      "${NUM_CONTAINERS}" "${ASSIGNATION_POLICY}" "${DYNAMIC_POWER_BUDGETS}"
  log_timestamp "${EXPERIMENT_NAME}" "stop"
  sleep 60
}
