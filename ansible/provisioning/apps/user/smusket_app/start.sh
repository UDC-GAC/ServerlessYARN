#!/usr/bin/env bash

OUTPUT_DIR="{{ bind_dir_on_container }}/{{ output_dir }}"

# CAUTION!! This script must only be executed from master container
#export MASTER_IP_ADDRESS=$(hostname -I | awk '{print $1}')
export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export OUTPUT_FILE="$OUTPUT_DIR/output_smusket_app_`date +%H-%M-%S`"
export RUNTIME_FILE="$OUTPUT_DIR/runtime_smusket_app_`date +%H-%M-%S`"

. "${SCRIPT_DIR}/files_dir/get-env.sh"

mkdir -p "${SMUSKET_OUTPUT}"
if [ ! -f "${SMUSKET_INPUT}" ]; then
  echo "SMusket input doesn't exist: ${SMUSKET_INPUT}"
  echo "Make sure to copy an input file to container bind directory"
  exit 1
fi

# Store data in HDFS for SMusket
echo "Copying SMusket input to HDFS..."
START=`date +%s.%N`
${HADOOP_HOME}/bin/hdfs dfs -mkdir "${SMUSKET_HDFS_BASE_PATH}"
${HADOOP_HOME}/bin/hdfs dfs -put "${SMUSKET_INPUT}" "${SMUSKET_HDFS_INPUT}"
END=`date +%s.%N`
echo "Smusket input successfully copied to HDFS"
echo "HDFS PUT EXECUTION TIME: $( echo "${END} - ${START}" | bc -l )" | tee -a "${SMUSKET_OUTPUT}/${RUNTIME_FILE}"

# Some sleep before start application
sleep 10

# Run SMusket
echo "Running SMusket"
START=`date +%s.%N`
"${SMUSKET_HOME}"/bin/smusketrun -sm "-i ${SMUSKET_HDFS_INPUT} -n 64 -k 25" \
  --master yarn \
  --deploy-mode cluster \
  # --conf "spark.local.dir=${SPARK_DATA_DIR}" \
  #--conf "spark.driver.host=${MASTER_IP_ADDRESS}"
END=`date +%s.%N`
echo "SMUSKET EXECUTION TIME: $( echo "${END} - ${START}" | bc -l )" | tee -a "${SMUSKET_OUTPUT}/${RUNTIME_FILE}"

# Get results from HDFS
START=`date +%s.%N`
$HADOOP_HOME/bin/hdfs dfs -get "${SMUSKET_HDFS_OUTPUT}" "${SMUSKET_OUTPUT}/${OUTPUT_FILE}"
END=`date +%s.%N`
echo "HDFS GET TIME: $( echo "${END} - ${START}" | bc -l )" | tee -a "${SMUSKET_OUTPUT}/${RUNTIME_FILE}"

