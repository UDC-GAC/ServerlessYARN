#!/bin/bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
PLATFORM_HOME=$(dirname "${SCRIPT_DIR}")
TESTS_DIR="${PLATFORM_HOME}/ansible/provisioning/tests/power_budgeting"
RAW_RESULTS_DIR="${TESTS_DIR}/out"
RESULTS_DIR="${TESTS_DIR}/PowerBudgetingExperiments/EXTRA_EXPERIMENTS"
PLATFORM_INSTALL_DIR="${HOME}/ServerlessYARN_install"

echo "SCRIPT_DIR = ${SCRIPT_DIR}"
echo "PLATFORM_HOME = ${PLATFORM_HOME}"
echo "TESTS_DIR = ${TESTS_DIR}"
echo "RESULTS_DIR = ${RESULTS_DIR}"
echo "RAW_RESULTS_DIR = ${RAW_RESULTS_DIR}"
echo "PLATFORM_INSTALL_DIR = ${PLATFORM_INSTALL_DIR}"

SLURM_JOB_SCRIPT="sbatch_run_tests.sh"
NUM_TESTS=10
SLEEP_BETWEEN_JOBS=120

for i in $(seq 0 $(( NUM_TESTS - 1 ))); do
    echo "[$(date -u)] Launching test ${i}..."

    SLURM_JOB_ID=$(sbatch --parsable "${SCRIPT_DIR}/${SLURM_JOB_SCRIPT}")
    echo "[$(date -u)] SLURM job launched with JOBID: ${SLURM_JOB_ID}"

    # Wait for job to finish
    while squeue -j "${SLURM_JOB_ID}" >> /dev/null 2>&1; do
        echo "[$(date -u)] Waiting for job ${SLURM_JOB_ID} to finish..."
        sleep 600
    done

    echo "[$(date -u)] Job ${SLURM_JOB_ID} has finished. Copying results and cleaning..."

    sleep 10

    # Move results
    OUTPUT_DIR="${RESULTS_DIR}/RUN_${i}"
    mkdir -p "${OUTPUT_DIR}"
    mv "${RAW_RESULTS_DIR}"/* "${OUTPUT_DIR}"
    mv "${PLATFORM_HOME}/power_budgeting_tests.log" "${OUTPUT_DIR}"
    rm -rf "${PLATFORM_INSTALL_DIR}"

    echo "[$(date -u)] Results have been moved and installation directory has been removed. Going to sleep ${SLEEP_BETWEEN_JOBS} seconds between jobs"
    sleep "${SLEEP_BETWEEN_JOBS}"
done

echo "[$(date -u)] All the ${NUM_TESTS} tests has been executed"