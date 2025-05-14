#!/usr/bin/env bash

#########################################################################################################
# ENVIRONMENT
#########################################################################################################
export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
. "${SCRIPT_DIR}/bin/load-env.sh"

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
            echo "[$(date -u)] Running experiment ${EXPERIMENT_NAME} for app ${APP}"
            bash "${BIN_DIR}/run-experiment.sh" "${APP}" "${EXPERIMENT}" >> "${OUTPUT_DIR}/${APP}_${EXPERIMENT_NAME}.out" 2>&1
            if [ -f "${OUTPUT_DIR}/${APP}_${EXPERIMENT_NAME}.out" ]; then
              mv "${OUTPUT_DIR}/${APP}_${EXPERIMENT_NAME}.out" "${OUTPUT_DIR}/results_${APP}_${EXPERIMENT_NAME}/"
            fi
          else
            echo "[$(date -u)] Experiment ${EXPERIMENT_NAME} for app ${APP} not included"
          fi
      done
    else
      echo "[$(date -u)] Application ${APP} not included"
    fi
done

sleep 20