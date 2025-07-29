#!/usr/bin/env bash

function print_env() {
  echo "ENVIRONMENT FOR EXPERIMENT ${EXPERIMENT_NAME}"
  echo -e "\t* APP_NAME: ${APP_NAME}"
  echo -e "\t* APP_DIR: ${APP_DIR}"
  echo -e "\t* RULES_FILE: ${RULES_FILE}"
  echo -e "\t* SETUP_FILE: ${SETUP_FILE}"
  echo -e "\t* ENTRYPOINT_FILE: ${ENTRYPOINT_FILE}"
  echo -e "\t* PLOTS_CONFIG_FILE: ${PLOTS_CONFIG_FILE}"
  echo -e "\t* APP_CONFIG_FILE: ${APP_CONFIG_FILE}"
  echo -e "\t* BIN_DIR: ${BIN_DIR}"
  echo -e "\t* CONF_DIR: ${CONF_DIR}"
  echo -e "\t* TEST_DIR: ${TEST_DIR}"
  echo -e "\t* PROVISIONING_DIR: ${PROVISIONING_DIR}"
  echo -e "\t* ANSIBLE_DIR: ${ANSIBLE_DIR}"
  echo -e "\t* ANSIBLE_INVENTORY: ${ANSIBLE_INVENTORY}"
}

function change_npb_num_threads() {
  sed -i "s/^\(export NUM_THREADS=\)[0-9]\+$/\1${1}/" "${PROVISIONING_DIR}/apps/${APP_DIR}/runtime_files/get_env.sh"
}

function change_npb_kernel() {
  sed -i "s/^\(export NPB_KERNELS=\)(.*)/\1(${1})/" "${PROVISIONING_DIR}/apps/${APP_DIR}/runtime_files/get_env.sh"
}

function change_npb_class() {
  sed -i "s/^\(export NPB_CLASSES=\)(.*)/\1(${1})/" "${PROVISIONING_DIR}/apps/${APP_DIR}/runtime_files/get_env.sh"
}

function change_initial_allocation() {
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

function curl_wrapper() {
  STATUS_CODE=$("$@" 2>&1 | grep -oE '^[0-9]{3}')
  echo "${@} ${STATUS_CODE}"
}

function add_app() {
  local APP_DIR="${1}"
  python3 "${APP_MNG_DIR}/add-app-to-config.py" "${PROVISIONING_DIR}/config/config.yml" "${APP_DIR}"
  python3 "${PROVISIONING_DIR}/scripts/load_apps_from_config.py"
}

function run_app() {
  local APP_NAME="${1}"
  local EXPERIMENT_NAME="${2}"
  sleep 20
  python3 "${APP_MNG_DIR}/run-app.py" "${APP_NAME}" "${RESULTS_DIR}/${EXPERIMENT_NAME}" \
                                      "${NUM_CONTAINERS}" "${ASSIGNATION_POLICY}"
  sleep 60
}

function run_app_dynamic_pb() {
  local APP_NAME="${1}"
  local EXPERIMENT_NAME="${2}"
  local DYNAMIC_POWER_BUDGETS="${3}"
  sleep 20
  python3 "${APP_MNG_DIR}/run-app.py" "${APP_NAME}" "${RESULTS_DIR}/${EXPERIMENT_NAME}" \
                                      "${NUM_CONTAINERS}" "${ASSIGNATION_POLICY}" "${DYNAMIC_POWER_BUDGETS}"
  sleep 60
}
