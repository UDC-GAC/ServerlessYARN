#!/usr/bin/env bash

# File containing the config for each experiment with the following format:
#
#       NUM_THREADS,STATIC_MODEL,DYNAMIC_MODEL,HW_AWARE_MODEL
#
# These paramaters are:
#
# - NUM_THREADS: Currently used only for NPB applications where number of threads are specified through
#   an environment file.
#
# - STATIC_MODEL: Static power model (without support for online learning) used to do power budgeting.
#
# - DYNAMIC_MODEL: Dynamic power model (with support for online learning) used to do power budgeting.
#
# - STATIC_MODEL: HW aware model (with support to take into account the underlying architecture) used to
#   do power budgeting.
#
# NOTE: The name of the experiment must match one of the YAML files containing the configuration of an application
# for ServerlessYARN

declare -A EXPERIMENT_CONFIG

EXPERIMENT_CONFIG["1cont_1thread"]="1,polyreg_Single_Core,sgdregressor_Single_Core,multisocket_hw_aware"
EXPERIMENT_CONFIG["1cont_32threads"]="32,polyreg_General,sgdregressor_General,multisocket_hw_aware"
EXPERIMENT_CONFIG["1cont_64threads"]="64,polyreg_General,sgdregressor_General,multisocket_hw_aware"


# CAUTION!! Assuming 250W for Intel Xeon Silver 4216 (specification indicates 200W)
# SHARES_PER_WATT = cpu_max_shares / (max_energy - min_energy) =
#                   (num_threads * 100) / (tdp - min_measured_energy) = (64 * 100) / (250 - 20) = 27.83
export DYNAMIC_SHARES_PER_WATT=28