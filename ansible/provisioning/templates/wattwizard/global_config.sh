#!/usr/bin/env bash

confDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

export TRAIN_FILE_NAME="{{ train_file_name }}"
export TRAIN_FILE=${confDir}/"{{ train_file_name }}".timestamps
export MODEL_VARIABLES="{{ model_variables }}"
export PREDICTION_METHODS="{{ prediction_methods }}"
export INFLUXDB_BUCKET="{{ influxdb_bucket }}"
