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

EXPERIMENTS=($(jq -c -r '.[]' "${CONFIG_FILE}")) # Get experiment names
for EXPERIMENT_CONFIG in "${EXPERIMENTS[@]}"; do
    INCLUDE=$(echo "${EXPERIMENT_CONFIG}" | jq -r '.include')
    EXPERIMENT_NAME=$(echo "${EXPERIMENT_CONFIG}" | jq -r '.name')
    if [ "${INCLUDE}" == "yes" ]; then
      echo "[$(date -u)] Running experiment ${EXPERIMENT_NAME}"
      bash "${BIN_DIR}/run-experiment.sh" "${EXPERIMENT_CONFIG}" >> "${OUTPUT_DIR}/${EXPERIMENT_NAME}.out" 2>&1
      if [ -f "${OUTPUT_DIR}/${EXPERIMENT_NAME}.out" ]; then
        mv "${OUTPUT_DIR}/${EXPERIMENT_NAME}.out" "${OUTPUT_DIR}/${EXPERIMENT_NAME}/"
      fi
    else
      echo "[$(date -u)] Experiment ${EXPERIMENT_NAME} not included"
    fi
done

sleep 20