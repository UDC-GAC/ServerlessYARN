#!/usr/bin/env bash

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
DATA_DIR="${SCRIPT_DIR}/data"
NUM_CHUNKS=$(( $(nproc) * 2 ))
SPARK_VERSION="{{ spark_version }}"
HADOOP_VERSION="{{ hadoop_version }}"

# Create data directory
mkdir -p "${DATA_DIR}"

####################################################################################
# ADD TO THE MAPPING ANY LARGE FILES YOU MAY WANT TO USE INSIDE CONTAINERS
####################################################################################
# Mapping of external URLs and files
declare -A EXTERNAL_SOURCES=(
  # Spark (first file assumes Spark version compatible with hadoop 3.x)
  ["https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}"]="spark-${SPARK_VERSION}-bin-hadoop3.tgz,spark-${SPARK_VERSION}-bin-without-hadoop.tgz"
  # Hadoop
  ["https://archive.apache.org/dist/hadoop/core/hadoop-${HADOOP_VERSION}"]="hadoop-${HADOOP_VERSION}.tar.gz"
  # NAS Parallel Benchmarks
  ["https://www.nas.nasa.gov/assets/nas/npb"]="NPB3.4.2.tar.gz"
)

for BASE_URL in "${!EXTERNAL_SOURCES[@]}"; do
  IFS=',' read -ra EXTERNAL_FILES <<< "${EXTERNAL_SOURCES[${BASE_URL}]}"
  for FILENAME in "${EXTERNAL_FILES[@]}"; do
    FULL_URL="${BASE_URL}/${FILENAME}"
    OUTPUT_FILE="${DATA_DIR}/${FILENAME}"
    if [ ! -f "${OUTPUT_FILE}" ]; then
      bash "${SCRIPT_DIR}/parallel_curl.sh" "${FULL_URL}" "${OUTPUT_FILE}" "${NUM_CHUNKS}"
      echo "Successfully downloaded: ${FILENAME}"
    fi
  done
done

####################################################################################
# PEXELS VIDEOS
####################################################################################
# Pexels videos are handled separately using wget (parallel curl is not needed and it shows some problems)
# Download Pexels videos in different resolutions: 360p, 540p, 720p and 1080p
declare -A RESOLUTIONS=(["360"]="640" ["540"]="960" ["720"]="1280" ["1080"]="1920")
declare -A PEXELS_VIDEOS=(
  ["frog1"]="855631"
  ["frog2"]="2422933"
  ["frog3"]="5450486"
  ["frog4"]="12516136"
  ["frog5"]="9083215"
  ["frog6"]="15996459"
)

# Create directory to store Pexels videos
mkdir -p "${DATA_DIR}/pexels"

for VIDEO_NAME in "${!PEXELS_VIDEOS[@]}"; do
  VIDEO_ID="${PEXELS_VIDEOS[${VIDEO_NAME}]}"
  for HEIGHT in "${!RESOLUTIONS[@]}"; do
    WIDTH="${RESOLUTION[${HEIGHT}]}"
    FILENAME="${VIDEO_NAME}-${HEIGHT}.mp4"
    OUTPUT_FILE="${DATA_DIR}/pexels/${FILENAME}"
    if [ ! -f "${OUTPUT_FILE}" ]; then
      wget -qO "${OUTPUT_FILE}" "https://www.pexels.com/es-es/download/video/${VIDEO_ID}/?h=${HEIGHT}&w=${WIDTH}"
      echo "Successfully downloaded: ${FILENAME}"
    fi
  done
done