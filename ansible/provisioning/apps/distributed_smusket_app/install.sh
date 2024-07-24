#!/usr/bin/env bash

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export FILES_DIR="${SCRIPT_DIR}/files_dir"
export DEBIAN_FRONTEND=noninteractive

apt-get -y update
apt-get -y install nano wget curl git openjdk-8-jdk python3 python3-pip openssh-client openssh-server

. "${FILES_DIR}/get-env.sh"

# Setup SSH
mkdir /run/sshd
chmod 0711 /run/sshd

# Install Hadoop
wget "https://archive.apache.org/dist/hadoop/core/hadoop-${HADOOP_VERSION}/${HADOOP_TAR_FILE}"
tar -xf "${HADOOP_TAR_FILE}" -C /opt
chown -R $(whoami):$(whoami) "${HADOOP_HOME}"

# Configure Hadoop
HADOOP_CONFIG_FILES=("hdfs-site.xml" "core-site.xml" "yarn-site.xml" "hadoop-env.sh")
for FILE in "${HADOOP_CONFIG_FILES[@]}"; do
  cp "${FILES_DIR}/hadoop/${FILE}" "${HADOOP_HOME}/etc/hadoop/${FILE}"
done

# Install Spark
wget "https://dlcdn.apache.org/spark/spark-${SPARK_VERSION}/${SPARK_TAR_FILE}"
tar -xf "${SPARK_TAR_FILE}" -C /opt
rm "${SPARK_TAR_FILE}"

# Configure Spark
cp "${FILES_DIR}/spark/spark-defaults.conf" "${SPARK_HOME}/conf/spark-defaults.conf"
cp "${FILES_DIR}/spark/spark-env.sh" "${SPARK_HOME}/conf/spark-env.sh"

# Install SMusket
mkdir -p "${SMUSKET_HOME}"
git clone https://github.com/UDC-GAC/smusket.git "${SMUSKET_HOME}"

# Configure SMusket
cp "${FILES_DIR}/smusket.conf" "${SMUSKET_HOME}/etc/smusket.conf"