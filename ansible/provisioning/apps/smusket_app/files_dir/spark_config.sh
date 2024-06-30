export SPARK_VERSION="3.4.3"
export SPARK_TAR_FILE="spark-${SPARK_VERSION}-bin-hadoop${SPARK_VERSION:0:1}.tgz"
export SPARK_DATA_DIR={{ bind_dir_on_container }}
export SPARK_DATA_FILE="${SPARK_DATA_DIR}/ERR031558.fastq"