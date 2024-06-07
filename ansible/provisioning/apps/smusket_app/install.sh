#!/usr/bin/env bash

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

source "${SCRIPT_DIR}/files_dir/spark_config.sh"
source "${SCRIPT_DIR}/files_dir/smusket_config.sh"

# Install Spark
m_echo "Downloading Apache Spark..."
wget "https://dlcdn.apache.org/spark/spark-${SPARK_VERSION}/${SPARK_TAR_FILE}"
tar -xf "${SPARK_TAR_FILE}" -C "${SCRIPT_DIR}"
rm "${SPARK_TAR_FILE}"

# Install SMusket
mkdir -p "${SMUSKET_HOME}"
git clone https://github.com/UDC-GAC/smusket.git "${SMUSKET_HOME}"

# Configure SMusket
sed -i 's/^MERGE_OUTPUT=.*/MERGE_OUTPUT=true/' "${SMUSKET_HOME}"/etc/smusket.conf
sed -i 's/^SERIALIZED_RDD=.*/SERIALIZED_RDD=false/' "${SMUSKET_HOME}"/etc/smusket.conf
sed -i 's/^HDFS_BASE_PATH=.*/HDFS_BASE_PATH=\/scratch\/ssd/' "${SMUSKET_HOME}"/etc/smusket.conf