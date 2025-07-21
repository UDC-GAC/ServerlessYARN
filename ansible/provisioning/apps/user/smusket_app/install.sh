#!/usr/bin/env bash

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export FILES_DIR="${SCRIPT_DIR}/files_dir"
export DEBIAN_FRONTEND=noninteractive

. "${FILES_DIR}/get-env.sh"

# General dependencies
apt-get -y update
apt-get -y install nano curl git python3 python3-pip

# Install SMusket
mkdir -p "${SMUSKET_HOME}"
git clone https://github.com/UDC-GAC/smusket.git "${SMUSKET_HOME}"

# Configure SMusket
cp "${FILES_DIR}/smusket.conf" "${SMUSKET_HOME}/etc/smusket.conf"