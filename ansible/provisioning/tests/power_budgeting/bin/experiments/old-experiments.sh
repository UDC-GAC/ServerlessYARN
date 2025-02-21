#!/usr/bin/env bash

#########################################################################################################
# REMOVED EXPERIMENTS
#########################################################################################################

#########################################################################################################
# calibration: One execution first just to calibrate SmartWatts
#########################################################################################################
#mkdir -p "${RESULTS_DIR}/calibration"
#register_logs_position
#
# Deactivate Serverless
#curl_wrapper bash "${SC_SCRIPTS_DIR}/deactivate-service.sh" "Guardian"
#curl_wrapper bash "${SC_SCRIPTS_DIR}/deactivate-service.sh" "Scaler"
#run_app "${APP_NAME}" "calibration"
#sleep 30
#
#save_logs "calibration"

#########################################################################################################
# hw_aware_model: Run app with ServerlessContainers using HW aware power modelling
#########################################################################################################
#mkdir -p "${RESULTS_DIR}/hw_aware_model"
#register_logs_position
#
#curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model-reliability.sh" "low"
#curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "modelling"
#curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model.sh" "${HW_AWARE_POWER_MODEL}"
#run_app "${APP_NAME}" "hw_aware_model"
#
#save_logs "hw_aware_model"

#########################################################################################################
# serverless_dynamic_model: Run app with ServerlessContainers using power modelling and online learning
#########################################################################################################
#mkdir -p "${RESULTS_DIR}/serverless_dynamic_model"
#register_logs_position
#
#curl_wrapper bash "${SC_SCRIPTS_DIR}/activate-service.sh" "WattTrainer"
#curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model-reliability.sh" "low"
#curl_wrapper bash "${SC_SCRIPTS_DIR}/change-energy-rules-policy.sh" "modelling"
#curl_wrapper bash "${SC_SCRIPTS_DIR}/change-model.sh" "${DYNAMIC_POWER_MODEL}"
#run_app "${APP_NAME}" "serverless_dynamic_model"
#
#save_logs "serverless_dynamic_model"
