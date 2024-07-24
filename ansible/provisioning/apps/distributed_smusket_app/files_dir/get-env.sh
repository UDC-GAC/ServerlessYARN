# Hadoop
export HADOOP_VERSION={{ hadoop_version }}
export HADOOP_TAR_FILE="hadoop-${HADOOP_VERSION}.tar.gz"
export HADOOP_HOME=/opt/hadoop-${HADOOP_VERSION}
export HADOOP_CONF_DIR={{ bind_dir_on_container }}/hadoop/conf
export HADOOP_LOG_DIR={{ bind_dir_on_container }}/hadoop/logs
export HADOOP_NAMENODE_DIR={{ bind_dir_on_container }}/hadoop/hdfs/namenode
export HADOOP_DATANODE_DIR={{ bind_dir_on_container }}/hadoop/hdfs/datanode
export HADOOP_NODEMANAGER_DIR={{ bind_dir_on_container }}/hadoop/yarn/local

# Spark
export SPARK_VERSION={{ spark_version }}
export SPARK_TAR_FILE="spark-${SPARK_VERSION}-bin-hadoop${SPARK_VERSION:0:1}.tgz"
export SPARK_HOME=/opt/spark-${SPARK_VERSION}-bin-hadoop"${SPARK_VERSION:0:1}"
export SPARK_LOG_DIR={{ bind_dir_on_container }}/spark/logs
export SPARK_CONF_DIR={{ bind_dir_on_container }}/spark/conf
export SPARK_DATA_DIR={{ bind_dir_on_container }}/spark/data
export SPARK_WORKER_DIR={{ bind_dir_on_container }}/spark/worker

# SMusket
export SMUSKET_HOME=/opt/smusket
export SMUSKET_HDFS_BASE_PATH=/smusket
export SMUSKET_INPUT_FILE="ERR031558.fastq"
export SMUSKET_INPUT={{ bind_dir_on_container }}/${SMUSKET_INPUT_FILE}
export SMUSKET_OUTPUT={{ bind_dir_on_container }}/smusket-output
export SMUSKET_HDFS_INPUT="${SMUSKET_HDFS_BASE_PATH}/${SMUSKET_INPUT_FILE}"
export SMUSKET_HDFS_OUTPUT="${SMUSKET_HDFS_BASE_PATH}/SparkMusket/output/smusket/${SMUSKET_INPUT_FILE}.corrected"


# Python
export PYTHON_HOME="$(which python3)"

# Java JDK
export JAVA_HOME="$(dirname $(dirname $(readlink -f $(which java))))"
