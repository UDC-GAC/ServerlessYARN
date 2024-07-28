#!/usr/bin/env bash

# CAUTION!! This script must only be executed from master container
export MASTER_IP_ADDRESS=$(hostname -I | awk '{print $1}')
export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

. "${SCRIPT_DIR}/files_dir/get-env.sh"

mkdir -p "${SMUSKET_OUTPUT}"
if [ ! -f "${SMUSKET_INPUT}" ]; then
  echo "SMusket input doesn't exist: ${SMUSKET_INPUT}"
  echo "Make sure to copy an input file to container bind directory"
  exit 1
fi

# Configure HDFS input for SMusket
echo "Copying SMusket input to HDFS..."
START=`date +%s.%N`
${HADOOP_HOME}/bin/hadoop fs -mkdir "${SMUSKET_HDFS_BASE_PATH}"
${HADOOP_HOME}/bin/hadoop fs -put "${SMUSKET_INPUT}" "${SMUSKET_HDFS_INPUT}"
END=`date +%s.%N`
echo "Smusket input successfully copied to HDFS"
echo "HDFS PUT EXECUTION TIME: $( echo "${END} - ${START}" | bc -l )" | tee -a "${SMUSKET_OUTPUT}/results"

# Some sleep before start application
sleep 10

# Set Spark Driver config
export SPARK_LOCAL_IP="${MASTER_IP_ADDRESS}"
export SPARK_DRIVER_HOST="${MASTER_IP_ADDRESS}"

# Run SMusket
echo "Running SMusket"
START=`date +%s.%N`
"${SMUSKET_HOME}"/bin/smusketrun -sm "-i ${SMUSKET_HDFS_INPUT} -n 64 -k 25" \
  --master spark://${MASTER_IP_ADDRESS}:7077 \
  --deploy-mode client \
  --conf "spark.local.dir=${SPARK_DATA_DIR}" \
  --conf "spark.driver.host=${MASTER_IP_ADDRESS}"
END=`date +%s.%N`
echo "SMUSKET EXECUTION TIME: $( echo "${END} - ${START}" | bc -l )" | tee -a "${SMUSKET_OUTPUT}/results"

# Get results from HDFS
START=`date +%s.%N`
$HADOOP_HOME/bin/hdfs dfs -get "${SMUSKET_HDFS_OUTPUT}" "${SMUSKET_OUTPUT}"
END=`date +%s.%N`
echo "HDFS GET TIME: $( echo "${END} - ${START}" | bc -l )" | tee -a "${SMUSKET_OUTPUT}/results"

