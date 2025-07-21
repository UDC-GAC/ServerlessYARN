#!/usr/bin/env bash
cd {{ bind_dir_on_container }}
set -e

$HADOOP_HOME/bin/hdfs dfs -mkdir -p /user/root

## Download data from local HDFS (should have been previously downloaded from global HDFS)
$HADOOP_HOME/bin/hdfs dfs -get /user/root/input_data $HOME/input_data

## Modify downloaded data
echo "Test to upload data in HDFS: local --> global" >> $HOME/input_data

## Upload data to local HDFS (should be uploaded afterwards to global HDFS to persist it)
$HADOOP_HOME/bin/hdfs dfs -put $HOME/input_data /user/root/output_data
