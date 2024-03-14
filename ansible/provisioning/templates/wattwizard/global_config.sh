#!/usr/bin/env bash

confDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

export TRAIN_FILE_NAME="{{ config.train_file_name }}"
export TRAIN_FILE=${confDir}/"{{ config.train_file_name }}".timestamps
export MODEL_VARIABLES="{{ config.model_variables }}"
export PREDICTION_METHODS="{{ config.prediction_methods }}"
export INFLUXDB_BUCKET="{{ config.influxdb_bucket }}"
