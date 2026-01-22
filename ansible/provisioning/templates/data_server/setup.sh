#!/usr/bin/env bash

NUM_CHUNKS=$(( $(nproc) * 2 ))
SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
DATA_DIR="${SCRIPT_DIR}/data"
SOURCES_FILE="${SCRIPT_DIR}/sources.list"

# Create data directory
mkdir -p "${DATA_DIR}"

# Read sources list and get files
while read -r FILENAME URL; do
  OUTPUT_FILE="${DATA_DIR}/${FILENAME}"
  # Ensure the file doesn't already exist before proceeding with the download
  if [ ! -f "${OUTPUT_FILE}" ]; then
    SIZE=$(curl -sI "${URL}" | awk '/^Content-Length:/ {print $2}' | tr -d '\r')
    # Parallel curl needs to know the size of the file before proceeding
    if [ -z "${SIZE}" ] || [ "${SIZE}" -eq "0" ] || [ "${FILENAME}" == "NPB3.4.2.tar.gz" ]; then
      wget -qO "${OUTPUT_FILE}" "${URL}"
    else
      bash "${SCRIPT_DIR}/parallel_curl.sh" "${URL}" "${OUTPUT_FILE}" "${NUM_CHUNKS}"
    fi
    echo "Successfully downloaded file ${FILENAME} of size ${SIZE:-unknown}"
  fi
done < "${SOURCES_FILE}"