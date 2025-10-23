#!/usr/bin/env bash
cd {{ bind_dir_on_container }}
set -e

$HADOOP_HOME/bin/hdfs dfs -mkdir -p /user/{{ user_info.user_name }}

## Download data from local HDFS (should have been previously downloaded from global HDFS)
$HADOOP_HOME/bin/hdfs dfs -get /user/{{ user_info.user_name }}/input_data {{ user_home_on_container }}/input_data

## Modify downloaded data
echo "Test to upload data in HDFS: local --> global" >> {{ user_home_on_container }}/input_data

## Upload data to local HDFS (should be uploaded afterwards to global HDFS to persist it)
$HADOOP_HOME/bin/hdfs dfs -put {{ user_home_on_container }}/input_data /user/{{ user_info.user_name }}/output_data
