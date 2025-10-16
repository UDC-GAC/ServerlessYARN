#!/usr/bin/env bash

export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export INSTALL_FILES_DIR="${SCRIPT_DIR}/install_files"
export DEBIAN_FRONTEND=noninteractive

. "${INSTALL_FILES_DIR}/get_env.sh"

apt-get -y update
apt-get -y install build-essential wget gfortran libopenmpi-dev openmpi-bin

# Download NPB
{% if local_data_server -%}
### Take advantage of the local data server to speed up the download
wget -O "${NPB_TAR_FILE}" "http://${DATA_SERVER_IP}:${DATA_SERVER_PORT}/${NPB_TAR_FILE}"
{%- else -%}
wget -O "${NPB_TAR_FILE}" "${NPB_DOWNLOAD_URL}"
{%- endif %}

tar -xf "${NPB_TAR_FILE}" -C "${NPB_INSTALL_DIR}"
rm "${NPB_TAR_FILE}"

# Compile NPB OMP kernels
cd "${NPB_OMP_HOME}"
cp config/make.def.template config/make.def

# Add -mcmodel=medium to fix error "relocation truncated to fit" for IS kernel
sed -i 's/^CFLAGS\t=.*/CFLAGS\t= -O3 -fopenmp -mcmodel=medium/' config/make.def

# Compile all NPB kernels and classes
make clean
for KERNEL in "${NPB_KERNELS[@]}";do
  for CLASS in "${NPB_CLASSES[@]}";do
    make "${KERNEL}" CLASS="${CLASS}"
  done
done

# Workaround to grant access to NPB kernels
chmod -R 777 "${NPB_INSTALL_DIR}"
