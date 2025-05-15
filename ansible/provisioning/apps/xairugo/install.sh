#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive
export SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
export FILES_DIR="${SCRIPT_DIR}/files_dir"

. "${FILES_DIR}/get_env.sh"

apt-get -y update

## Utilities, you may install here other packages that you find useful
apt-get install -y nano vim htop stress curl libtbb-dev libcurl4 libcurl4-openssl-dev

### NPB ### 
apt-get -y install build-essential wget gfortran libopenmpi-dev openmpi-bin

# Download
cd /opt
#wget "https://www.nas.nasa.gov/assets/npb/NPB3.4.2.tar.gz"
wget http://server:9001/NPB3.4.2.tar.gz
mkdir npb && tar xf NPB3.4.2.tar.gz -C npb --strip-components 1
rm NPB3.4.2.tar.gz # DO NOT LEAVE THESE KIND OF FILES ON THE CONTAINER IMAGE

# Compile NPB OMP kernels
cd npb/NPB3.4-OMP
cp config/make.def.template config/make.def

# Add -mcmodel=medium to fix error "relocation truncated to fit" for IS kernel
sed -i 's/^CFLAGS\t=.*/CFLAGS\t= -O3 -fopenmp -mcmodel=medium/' config/make.def

make clean
for KERNEL in "${NPB_KERNELS_TO_INSTALL[@]}";do
    make "${KERNEL}" CLASS="A"
    make "${KERNEL}" CLASS="B"
    make "${KERNEL}" CLASS="C"
    make "${KERNEL}" CLASS="D"    
done


## Compile NPB-C kernels
cd /opt
wget http://server:9001/NPB3.0-omp-C-master.tar.gz
mkdir npb-C && tar xf NPB3.0-omp-C-master.tar.gz -C npb-C --strip-components 1
rm NPB3.0-omp-C-master.tar.gz
cd npb-C
make clean
make suite

## Spark
apt-get install -y openjdk-8-jdk
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

# Download
cd /opt
wget http://server:9001/spark-3.5.5-bin-hadoop3.tgz
#wget https://archive.apache.org/dist/spark/spark-3.5.5/spark-3.5.5-bin-hadoop3.tgz
mkdir spark && tar xf "spark-3.5.5-bin-hadoop3.tgz" -C spark --strip-components 1
rm spark-3.5.5-bin-hadoop3.tgz # DO NOT LEAVE THESE KIND OF FILES ON THE CONTAINER IMAGE
chown -R $(whoami):$(whoami) spark
