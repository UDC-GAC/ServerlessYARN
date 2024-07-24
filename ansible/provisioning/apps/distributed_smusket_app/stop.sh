#!/usr/bin/env bash

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

. "${SCRIPT_DIR}/files_dir/get-env.sh"

# Get results from HDFS
$HADOOP_HOME/bin/hdfs dfs -get "${SMUSKET_HDFS_BASE_PATH}/${SMUSKET_INPUT_FILE}.corrected"
mv "${SMUSKET_INPUT_FILE}.corrected" "${SMUSKET_OUTPUT}"

# Remove unnecesary files and make the remaining ones accessible from host
rm -rf "${SPARK_DATA_DIR}"/blockmgr* "${SPARK_DATA_DIR}"/spark-*
chmod -R 644 "${SPARK_DATA_DIR}"
