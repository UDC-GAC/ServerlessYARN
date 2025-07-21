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
wget https://archive.apache.org/dist/spark/spark-{{ spark_version }}/spark-{{ spark_version }}-bin-hadoop3.tgz
mkdir spark && tar xf "spark-{{ spark_version }}-bin-hadoop3.tgz" -C spark --strip-components 1
chown -R $(whoami):$(whoami) spark
