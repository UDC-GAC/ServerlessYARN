#!/usr/bin/env bash

# Setup environment
ENV_FILE=bashrc
#ENV_FILE=profile

# Java
echo export JAVA_HOME=$JAVA_HOME >> ~/.$ENV_FILE

# Hadoop
echo export HADOOP_HOME=$HADOOP_HOME >> ~/.$ENV_FILE
echo export HADOOP_CONF_DIR=$HADOOP_CONF_DIR >> ~/.$ENV_FILE
echo export HADOOP_LOG_DIR=$HADOOP_LOG_DIR >> ~/.$ENV_FILE

# YARN (if conf and log dir are undefined they will default to the hadoop ones)
#echo export YARN_CONF_DIR=$YARN_CONF_DIR >> ~/.$ENV_FILE
#echo export YARN_LOG_DIR=$YARN_LOG_DIR >> ~/.$ENV_FILE

## Hadoop and YARN users (required for hadoop 3.3.5+)
echo export HDFS_NAMENODE_USER=$HDFS_NAMENODE_USER >> ~/.$ENV_FILE
echo export HDFS_DATANODE_USER=$HDFS_DATANODE_USER >> ~/.$ENV_FILE
echo export HDFS_SECONDARYNAMENODE_USER=$HDFS_SECONDARYNAMENODE_USER >> ~/.$ENV_FILE
echo export YARN_RESOURCEMANAGER_USER=$YARN_RESOURCEMANAGER_USER >> ~/.$ENV_FILE
echo export YARN_NODEMANAGER_USER=$YARN_NODEMANAGER_USER >> ~/.$ENV_FILE

# Zookeeper
echo export ZOO_LOG_DIR=$ZOO_LOG_DIR >> ~/.$ENV_FILE

# Spark
echo export SPARK_HOME=$SPARK_HOME >> ~/.$ENV_FILE
echo export SPARK_DIST_CLASSPATH=$SPARK_DIST_CLASSPATH >> ~/.$ENV_FILE
echo export SPARK_CONF_DIR=$SPARK_CONF_DIR >> ~/.$ENV_FILE

# Path
echo export PATH=$PATH:$HADOOP_HOME/bin >> ~/.$ENV_FILE

cp ~/.$ENV_FILE ~/.profile

## Run SSH server
/usr/sbin/sshd

## Setup passwordless ssh
ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 0600 ~/.ssh/authorized_keys
ssh-keyscan -t rsa localhost >> ~/.ssh/known_hosts
ssh-keyscan -t rsa 0.0.0.0 >> ~/.ssh/known_hosts
