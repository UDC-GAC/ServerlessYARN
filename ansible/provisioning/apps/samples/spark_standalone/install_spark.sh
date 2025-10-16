#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive

apt-get -y update

## Prerequisites
apt-get install -y curl wget

## Other utilities (you may install here other packages that you find useful)
apt-get install -y nano

## Java
apt-get install -y openjdk-8-jdk
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

## Spark
cd /opt
spark_download_file=spark-{{ spark_version }}-bin-hadoop3.tgz
{% if local_data_server -%}
### Take advantage of the local data server to speed up the download
wget -O $spark_download_file "http://${DATA_SERVER_IP}:${DATA_SERVER_PORT}/$spark_download_file"
{%- else -%}
### Take advantage of the parallel script included in BDWatchdog to speed up the download
spark_download_dir=https://archive.apache.org/dist/spark/spark-{{ spark_version }}
parallel_script_path=/opt/BDWatchdog/deployment/metrics/parallel_curl.sh
number_of_chunks=$(( $(nproc) * 2 ))
bash $parallel_script_path $spark_download_dir/$spark_download_file $spark_download_file "${number_of_chunks}"
{%- endif %}

mkdir spark && tar xf $spark_download_file -C spark --strip-components 1 && rm $spark_download_file
chown -R $(whoami):$(whoami) spark
