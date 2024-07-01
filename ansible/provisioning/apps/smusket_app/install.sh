#!/usr/bin/env bash

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export FILES_DIR="${SCRIPT_DIR}/files_dir"
export DEBIAN_FRONTEND=noninteractive

apt-get -y update
apt-get -y install wget git openjdk-8-jdk python3 python3-pip

. "${FILES_DIR}/spark_config.sh"
. "${FILES_DIR}/get_env.sh"

# Install Spark
wget "https://dlcdn.apache.org/spark/spark-${SPARK_VERSION}/${SPARK_TAR_FILE}"
tar -xf "${SPARK_TAR_FILE}" -C "${SCRIPT_DIR}"
rm "${SPARK_TAR_FILE}"

# Configure Spark
cp "${FILES_DIR}/spark-defaults.conf" "${SPARK_CONF_DIR}/spark-defaults.conf"

# Install SMusket
mkdir -p "${SMUSKET_HOME}"
git clone https://github.com/UDC-GAC/smusket.git "${SMUSKET_HOME}"

# Configure SMusket
sed -i 's/^MERGE_OUTPUT=.*/MERGE_OUTPUT=true/' "${SMUSKET_HOME}"/etc/smusket.conf
sed -i 's/^SERIALIZED_RDD=.*/SERIALIZED_RDD=false/' "${SMUSKET_HOME}"/etc/smusket.conf
sed -i 's/^HDFS_BASE_PATH=.*/HDFS_BASE_PATH=\/opt\/bind/' "${SMUSKET_HOME}"/etc/smusket.conf