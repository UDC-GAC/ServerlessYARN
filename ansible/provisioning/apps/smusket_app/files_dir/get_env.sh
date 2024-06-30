# Spark
export SPARK_HOME="${SCRIPT_DIR}"/spark-${SPARK_VERSION}-bin-hadoop"${SPARK_VERSION:0:1}"
export SPARK_CONF_DIR="${SPARK_HOME}/conf"

# SMusket
export SMUSKET_HOME="${SCRIPT_DIR}"/smusket

# Python
export PYTHON_HOME="$(which python3)"

# Java JDK
export JAVA_HOME="$(dirname $(dirname $(readlink -f $(which java))))"