#!/usr/bin/env bash
cd {{ bind_dir_on_container }}
set -e

# Mode of transfering data to/from global HDFS
## 0: only access local HDFS --> this requires previously transfering the input data from global HDFS and posteriosly transfering the output data to global HDFS
## 1: direct transfer --> transfer data from/to global HDFS directly
## 2: RBF transfer --> transfer data from/to global HDFS through a router-based federated HDFS cluster
DATA_TRANSFER=0

case $DATA_TRANSFER in
    0)
        INPUT_DATA_PREFIX=/user/{{ user_info.user_name }}
        OUTPUT_DATA_PREFIX=/user/{{ user_info.user_name }}
        $HADOOP_HOME/bin/hdfs dfs -mkdir -p $OUTPUT_DATA_PREFIX
        ;;
    1)
        GLOBAL_NAMENODE_IP=$(getent hosts {{ namenode_container_name }} | awk '{print $1 }' | head -n 1)
        INPUT_DATA_PREFIX=hdfs://$GLOBAL_NAMENODE_IP/global_data
        OUTPUT_DATA_PREFIX=hdfs://$GLOBAL_NAMENODE_IP/global_data
        ;;
    2)
        INPUT_DATA_PREFIX=/global_data
        OUTPUT_DATA_PREFIX=/global_data
        ;;
    *)
        echo "Unhandled value $DATA_TRANSFER"
        exit 2
esac

## Download data
$HADOOP_HOME/bin/hdfs dfs -get $INPUT_DATA_PREFIX/input_data {{ user_home_on_container }}/input_data

## Modify downloaded data
echo "Test to upload data in HDFS: local --> global" >> {{ user_home_on_container }}/input_data

## Upload data
$HADOOP_HOME/bin/hdfs dfs -put {{ user_home_on_container }}/input_data $OUTPUT_DATA_PREFIX/output_data
