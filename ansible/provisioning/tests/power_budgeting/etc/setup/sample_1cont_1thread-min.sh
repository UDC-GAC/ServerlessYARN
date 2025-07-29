#!/usr/bin/env bash

#########################################################################################################
# EXPERIMENT CONFIGURATION
#########################################################################################################
export INITIAL_CPU_ALLOCATION="min"
export NUM_CONTAINERS=1
export ASSIGNATION_POLICY="Best-effort"
export TIMEOUT_SECONDS=120
export CORES_TO_STRESS=1

# Configuration of the power-capping methods that will be used in this experiment
export EMPIRICAL_SHARES_PER_WATT="5" # Ratio used for empirical-value method in entrypoint
export TDP_SHARES_PER_WATT="28" # Ratio used for tdp-value method in entrypoint
export STATIC_POWER_MODEL="polyreg_Single_Core" # Power model used for model_boosted method in entrypoint

# Set cores to stress in the sample app runtime configuration
sed -i "s/^\(CORES_TO_STRESS=\)[0-9]\+$/\1${CORES_TO_STRESS}/" "${PROVISIONING_DIR}/apps/${APP_DIR}/runtime_files/app_config.sh"

# Set timeout in the sample app runtime configuration
sed -i "s/^\(TIMEOUT_SECONDS=\)[0-9]\+$/\1${TIMEOUT_SECONDS}/" "${PROVISIONING_DIR}/apps/${APP_DIR}/runtime_files/app_config.sh"