#!/usr/bin/env bash
cd {{ bind_dir_on_container }}
set -e

DIRECT_TRANSFER=1  # transfer data from/to global HDFS directly or through the local HDFS as an intermediary

if [ $DIRECT_TRANSFER == 1 ]
then
    GLOBAL_NAMENODE_IP=$(getent hosts {{ namenode_container_name }} | awk '{print $1 }' | head -n 1)
    INPUT_DATA_PREFIX=hdfs://$GLOBAL_NAMENODE_IP
fi

## Download data
$HADOOP_HOME/bin/hdfs dfs -get $INPUT_DATA_PREFIX/user/{{ user_info.user_name }}/input_data {{ user_home_on_container }}/input_data

## Modify downloaded data
echo "Test to upload data in HDFS: local --> global" >> {{ user_home_on_container }}/input_data

## Upload data
$HADOOP_HOME/bin/hdfs dfs -put {{ user_home_on_container }}/input_data $INPUT_DATA_PREFIX/user/{{ user_info.user_name }}/output_data
