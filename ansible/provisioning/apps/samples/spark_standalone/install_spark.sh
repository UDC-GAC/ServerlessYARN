#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive

apt-get -y update

## Prerequisites
apt-get install -y wget

## Other utilities (you may install here other packages that you find useful)
apt-get install -y nano

## Java
apt-get install -y openjdk-8-jdk
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

## Spark
cd /opt
spark_download_dir=https://archive.apache.org/dist/spark/spark-{{ spark_version }}
spark_download_file=spark-{{ spark_version }}-bin-hadoop3.tgz
wget $spark_download_dir/$spark_download_file
mkdir spark && tar xf $spark_download_file -C spark --strip-components 1 && rm $spark_download_file
chown -R $(whoami):$(whoami) spark
