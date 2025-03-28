#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive
export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export FILES_DIR="${SCRIPT_DIR}/myfiles"

. "${FILES_DIR}/get_env.sh"

apt-get -y update

## Utilities, you may install here other packages that you find useful
apt-get install -y nano vim htop stress

# For NPB
apt-get -y install build-essential wget gfortran libopenmpi-dev openmpi-bin

# Download NPB
wget "${NPB_DOWNLOAD_URL}"
tar -xf "${NPB_TAR_FILE}" -C "${NPB_INSTALL_DIR}"
rm "${NPB_TAR_FILE}"

# Compile NPB OMP kernels
cd "${NPB_OMP_HOME}"
cp config/make.def.template config/make.def

# Add -mcmodel=medium to fix error "relocation truncated to fit" for IS kernel
sed -i 's/^CFLAGS\t=.*/CFLAGS\t= -O3 -fopenmp -mcmodel=medium/' config/make.def

make clean
for KERNEL in "${NPB_KERNELS_TO_INSTALL[@]}";do
    make "${KERNEL}" CLASS="${NPB_CLASS}"
done


## Java
apt-get install -y openjdk-8-jdk
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

## Spark
cd /opt
wget https://archive.apache.org/dist/spark/spark-{{ spark_version }}/spark-{{ spark_version }}-bin-hadoop3.tgz
mkdir spark && tar xf "spark-{{ spark_version }}-bin-hadoop3.tgz" -C spark --strip-components 1
chown -R $(whoami):$(whoami) spark
