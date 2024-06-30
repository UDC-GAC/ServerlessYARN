#!/usr/bin/env bash

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

. "${SCRIPT_DIR}/files_dir/spark_config.sh"
. "${SCRIPT_DIR}/files_dir/get_available_threads.sh"
. "${SCRIPT_DIR}/files_dir/get_env.sh"

function set_n_cores() {
  MIN=$1
  OFFSET=$2
  MAX=$(( MIN + OFFSET ))
  CURRENT_CORES=""
  for (( i=MIN; i<MAX; i++ )); do
    if [ "${i}" -ne "${MIN}" ]; then
      CURRENT_CORES+=","
    fi
    CURRENT_CORES+="${i}"
  done
}

if [ ! -f "${SPARK_DATA_FILE}" ]; then
  echo "Spark data file doesn't exist: ${SPARK_DATA_FILE}"
  echo "Please rename SPARK_DATA_DIR and SPARK_DATA_FILE vars in ${FILES_DIR}/spark_config.sh"
  exit 1
fi

# Clean any previous Spark files
rm -rf "${SPARK_DATA_DIR}"/blockmgr* "${SPARK_DATA_DIR}"/spark-*

# Get the nearest power of 2 to MAX_THREADS as NUM_THREADS
NEAREST_TWO_POWER=$(echo "l(${MAX_THREADS})/l(2)" | bc -l | awk '{printf("%d\n",$1)}')
NUM_THREADS=$(echo "2^${NEAREST_TWO_POWER}" | bc -l)

# Some sleep before start application
sleep 10

# Set cores list
set_n_cores ${FIRST_THREAD} ${NUM_THREADS}

# Run SMusket using NUM_THREADS
echo "Running SMusket with ${NUM_THREADS} threads using cores = ${CURRENT_CORES}"
taskset -c "${CURRENT_CORES}" "${SMUSKET_HOME}"/bin/smusketrun -sm "-i ${SPARK_DATA_FILE} -n 64 -k 25" --conf "spark.local.dir=${SPARK_DATA_DIR}" --master local["${NUM_THREADS}"] --driver-memory 200g

# Some sleep after application execution
sleep 10

# Remove unnecesary files and make the remaining ones accessible from host
rm -rf "${SPARK_DATA_DIR}"/blockmgr* "${SPARK_DATA_DIR}"/spark-*
chmod -R 777 "${SPARK_DATA_DIR}"
