#!/usr/bin/env bash

## Setup environment (for some reason, bashrc works for 2.9.2 but not 3.3.4 and viceversa with profile)
ENV_FILE=bashrc
#ENV_FILE=profile
# Java
echo export JAVA_HOME=$JAVA_HOME >> ~/.$ENV_FILE
# Hadoop
echo export HADOOP_HOME=$HADOOP_HOME >> ~/.$ENV_FILE
echo export HADOOP_CONF_DIR=$HADOOP_CONF_DIR >> ~/.$ENV_FILE
echo export YARN_CONF_DIR=$YARN_CONF_DIR >> ~/.$ENV_FILE
echo export HADOOP_LOG_DIR=$HADOOP_LOG_DIR >> ~/.$ENV_FILE
echo export YARN_LOG_DIR=$YARN_LOG_DIR >> ~/.$ENV_FILE
# Hadoop users (needed for hadoop 3.3.4)
#echo export HDFS_NAMENODE_USER=$HDFS_NAMENODE_USER >> ~/.$ENV_FILE
#echo export HDFS_DATANODE_USER=$HDFS_DATANODE_USER >> ~/.$ENV_FILE
#echo export HDFS_SECONDARYNAMENODE_USER=$HDFS_SECONDARYNAMENODE_USER >> ~/.$ENV_FILE
#echo export YARN_RESOURCEMANAGER_USER=$YARN_RESOURCEMANAGER_USER >> ~/.$ENV_FILE
#echo export YARN_NODEMANAGER_USER=$YARN_NODEMANAGER_USER >> ~/.$ENV_FILE

## Run SSH server
/usr/sbin/sshd

## Setup passwordless ssh
ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 0600 ~/.ssh/authorized_keys
ssh-keyscan -t rsa localhost >> ~/.ssh/known_hosts
ssh-keyscan -t rsa 0.0.0.0 >> ~/.ssh/known_hosts

## Increase hadoop performance
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag

## Run hadoop services
#cd $HADOOP_HOME
#bash format_filesystem.sh
#sbin/start-dfs.sh
