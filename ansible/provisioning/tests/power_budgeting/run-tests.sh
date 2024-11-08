#!/usr/bin/env bash

#########################################################################################################
# APPS AND EXPERIMENTS
#########################################################################################################
APPS=("npb")
declare -A APP_EXPERIMENTS=(
  ["npb"]="1cont_1thread,1cont_32threads,1cont_64threads"
  ["hadoop"]="2cont_nthreads"
)

#########################################################################################################
# ENVIRONMENT
#########################################################################################################
export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export BIN_DIR="${SCRIPT_DIR}/bin"
export CONF_DIR="${SCRIPT_DIR}/etc"
export OUTPUT_DIR="${SCRIPT_DIR}/out"
export APP_CONFIG_DIR="${SCRIPT_DIR}/apps"
export TEST_DIR=$(dirname "${SCRIPT_DIR}")
export PROVISIONING_DIR=$(dirname "${TEST_DIR}")
export ANSIBLE_DIR=$(dirname "${PROVISIONING_DIR}")
export ANSIBLE_INVENTORY="${ANSIBLE_DIR}/ansible.inventory"
export SC_INSTALLATION_PATH="${HOME}/ServerlessYARN_install/ServerlessContainers/"

#########################################################################################################
# RUN TESTS
#########################################################################################################
mkdir -p "${OUTPUT_DIR}"

# Set ServerlessYARN configuration
cp "${CONF_DIR}/config.yml" "${PROVISIONING_DIR}/config/config.yml"

echo "Launch ServerlessYARN"
bash "${PROVISIONING_DIR}/scripts/start_all.sh"

# Let the platform 5 minutes to stabilise
sleep 300

for APP in "${APPS[@]}"; do
    echo "Current application: ${APP}"
    IFS=',' read -ra EXPERIMENTS <<< "${APP_EXPERIMENTS[${APP}]}"
    for EXPERIMENT in "${EXPERIMENTS[@]}"; do
        echo "Running experiment ${EXPERIMENT} for app ${APP}"
        bash "${BIN_DIR}/run-experiment.sh" "${APP}" "${EXPERIMENT}" >> "${OUTPUT_DIR}/${APP}_${EXPERIMENT}.out" 2>&1
    done
done

# Keep SLURM job active just in case an error has occurred during execution
sleep 259200