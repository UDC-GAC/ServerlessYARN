#!/usr/bin/env bash

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export RUNTIME_FILES_DIR="${SCRIPT_DIR}/runtime_files"

. "${RUNTIME_FILES_DIR}/get_env.sh"

# If some kernels are specified, overwrite default kernels
if [ -n "${1}" ];then
  IFS=',' read -ra NPB_KERNELS <<< "${1}"
fi

# If a number of threads is specified, overwrite NUM_THREADS
if [ -n "${2}" ];then
  NUM_THREADS="${2}"
fi

# Clean/Create output directory
rm -rf "${NPB_OUTPUT_DIR}/*"
mkdir -p "${NPB_OUTPUT_DIR}"

echo "Starting kernels execution"
for KERNEL in "${NPB_KERNELS[@]}";do
  for CLASS in "${NPB_CLASSES[@]}";do
    # Set number of threads
    export OMP_NUM_THREADS="${NUM_THREADS}"

    echo "[$(date -u "+%Y-%m-%d %H:%M:%S%z")] Running kernel ${KERNEL} (class=${NPB_CLASS}) with ${NUM_THREADS} threads" | tee -a "${NPB_OUTPUT_DIR}/results.log"
    # Run kernel
    START_TEST=$(date +%s%N)
    ${NPB_OMP_HOME}/bin/${KERNEL}.${NPB_CLASS}.x >> "${NPB_OUTPUT_DIR}/${KERNEL}-output.log" 2>&1
    END_TEST=$(date +%s%N)
    EXECUTION_TIME=$(bc <<< "scale=9; $(( END_TEST - START_TEST )) / 1000000000")

    # Log results
    echo "[$(date -u "+%Y-%m-%d %H:%M:%S%z")] Execution time for kernel ${KERNEL} (class=${NPB_CLASS}) with ${NUM_THREADS} thread(s): ${EXECUTION_TIME}" | tee -a "${NPB_OUTPUT_DIR}/results.log"

    # Sleep 5 minutes between executions
    #sleep 300
    sleep 10
  done
done

# Grant permissions to access results outside the container
chmod -R 777 "${NPB_OUTPUT_DIR}"