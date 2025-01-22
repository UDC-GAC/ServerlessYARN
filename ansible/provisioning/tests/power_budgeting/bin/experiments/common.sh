#!/usr/bin/env bash

# Dictionary with current CPU values to test
declare -A CPU_CURRENT_VALUES=(
  ["min"]="int(cont[\"cpu_min\"])"
  ["medium"]="(int(cont[\"cpu_max\"]) - int(cont[\"cpu_min\"])) \/\/ 2"
  ["max"]="int(cont[\"cpu_max\"])"
)

# Dictionary to save the position of the logs from some ServerlessContainers services
declare -A SC_LOGS_START=(
  ["guardian"]="0"
  ["scaler"]="0"
)
