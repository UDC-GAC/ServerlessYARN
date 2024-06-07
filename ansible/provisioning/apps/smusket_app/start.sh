#!/usr/bin/env bash

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

source "${SCRIPT_DIR}/files_dir/spark_config.sh"
source "${SCRIPT_DIR}/files_dir/smusket_config.sh"

function set_n_cores() {
  N=$1
  CURRENT_CORES=""
  for (( i=0; i<N; i++ )); do
    if [ "$i" -ne 0 ]; then
      CURRENT_CORES+=","
    fi
    CURRENT_CORES+="${CORES_ARRAY[i]}"
  done
}

if [ ! -f "${SPARK_DATA_FILE}" ]; then
  echo "Spark data file doesn't exist: ${SPARK_DATA_FILE}"
  echo "Please rename SPARK_DATA_DIR and SPARK_DATA_FILE vars in ${SCRIPT_DIR}/files_dir/spark_config.sh"
  exit 1
fi

CURRENT_CORES=""
CORES_ARRAY_LENGTH=${#CORES_ARRAY[@]}
NUM_THREADS=1
MAX_THREADS=$(( MAX_CORES < CORES_ARRAY_LENGTH ? MAX_CORES : CORES_ARRAY_LENGTH ))

sleep 10
while [ "${NUM_THREADS}" -le "${MAX_THREADS}" ]
do
  echo "Running SMusket with ${NUM_THREADS} threads"
  set_n_cores ${NUM_THREADS}
  taskset -c "${CURRENT_CORES}" "${SMUSKET_HOME}"/bin/smusketrun -sm "-i ${SPARK_DATA_FILE} -n 64 -k 25" --conf "spark.local.dir=${SPARK_DATA_DIR}" --master local["${NUM_THREADS}"] --driver-memory 200g
  rm -rf "${SPARK_DATA_DIR}"/blockmgr* "${SPARK_DATA_DIR}"/spark-*
  NUM_THREADS=$(( NUM_THREADS * 2 ))
  sleep 20
done
