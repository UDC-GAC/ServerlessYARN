#!/usr/bin/env bash

#########################################################################################################
# ENVIRONMENT
#########################################################################################################
export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export BIN_DIR="${SCRIPT_DIR}/bin"
export SC_MNG_DIR="${BIN_DIR}/serverless_containers"
export APP_MNG_DIR="${BIN_DIR}/app_management"
export EXPERIMENTS_DIR="${BIN_DIR}/experiments"
export CONF_DIR="${SCRIPT_DIR}/etc"
export CONFIG_FILE="${CONF_DIR}/experiments.json"
export OUTPUT_DIR="${SCRIPT_DIR}/out"
export APPS_CONFIG_DIR="${SCRIPT_DIR}/apps"
export APPS_RULES_DIR="${SCRIPT_DIR}/rules"
export TEST_DIR=$(dirname "${SCRIPT_DIR}")
export PROVISIONING_DIR=$(dirname "${TEST_DIR}")
export ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
export ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"
export SC_YARN_PATH="${HOME}/ServerlessYARN_install"
export SC_INSTALLATION_PATH="${SC_YARN_PATH}/ServerlessContainers"

#########################################################################################################
# PREREQUISITES
#########################################################################################################
# Check jq is installed, it is also installed by ServerlessYARN, but if we start the platform from scratch
# it might not be installed
which jq >/dev/null 2>&1
if [ $? -ne 0 ]; then
  curl -sS https://webi.sh/jq | bash
  cd "${HOME}" && rmdir -p Downloads/webi/jq/*
  cd "${SCRIPT_DIR}"
fi

#########################################################################################################
# RUN TESTS
#########################################################################################################
# Create output directory
mkdir -p "${OUTPUT_DIR}"

# Set ServerlessYARN configuration
cp "${CONF_DIR}/serverless_yarn_config.yml" "${PROVISIONING_DIR}/config/config.yml"

echo "Launch ServerlessYARN"
bash "${PROVISIONING_DIR}/scripts/start_all.sh"

# Let the platform 5 minutes to stabilise
sleep 300

APPS=($(jq -c -r '.apps[].app' "${CONFIG_FILE}")) # Get app names
for APP in "${APPS[@]}"; do
    INCLUDE_APP=$(jq -r ".apps[] | select(.app == \"${APP}\") | .include" "${CONFIG_FILE}")
    if [ "${INCLUDE_APP}" == "yes" ]; then
      echo "Current application: ${APP}"
      EXPERIMENTS=($(jq -c ".apps[] | select(.app == \"${APP}\") | .experiments[]" "${CONFIG_FILE}"))
      for EXPERIMENT in "${EXPERIMENTS[@]}"; do
          EXPERIMENT_NAME=$(echo "$EXPERIMENT" | jq -r '.name')
          INCLUDE_EXP=$(echo "$EXPERIMENT" | jq -r '.include')
          if [ "${INCLUDE_EXP}" == "yes" ]; then
            echo "Running experiment ${EXPERIMENT_NAME} for app ${APP}"
            bash "${BIN_DIR}/run-experiment.sh" "${APP}" "${EXPERIMENT}" >> "${OUTPUT_DIR}/${APP}_${EXPERIMENT_NAME}.out" 2>&1
            if [ -f "${OUTPUT_DIR}/${APP}_${EXPERIMENT_NAME}.out" ]; then
              mv "${OUTPUT_DIR}/${APP}_${EXPERIMENT_NAME}.out" "${OUTPUT_DIR}/results_${APP}_${EXPERIMENT_NAME}/"
            fi
          else
            echo "Experiment ${EXPERIMENT_NAME} for app ${APP} not included"
          fi
      done
    else
      echo "Application ${APP} not included"
    fi
done

sleep 20