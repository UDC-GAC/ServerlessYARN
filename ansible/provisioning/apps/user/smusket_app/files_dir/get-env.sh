# SMusket
export SMUSKET_HOME=/opt/smusket
export SMUSKET_HDFS_BASE_PATH=/smusket
export SMUSKET_INPUT_FILE="ERR031558.fastq"
export SMUSKET_INPUT={{ bind_dir_on_container }}/${SMUSKET_INPUT_FILE}
export SMUSKET_OUTPUT={{ bind_dir_on_container }}/smusket-output
export SMUSKET_HDFS_INPUT="${SMUSKET_HDFS_BASE_PATH}/${SMUSKET_INPUT_FILE}"
export SMUSKET_HDFS_OUTPUT="${SMUSKET_HDFS_BASE_PATH}/SparkMusket/output/smusket/${SMUSKET_INPUT_FILE}.corrected"

# Python
#export PYTHON_HOME="$(which python3)"

# Java JDK
#export JAVA_HOME="$(dirname $(dirname $(readlink -f $(which java))))"
