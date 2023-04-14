#!/usr/bin/env bash

$HADOOP_HOME/bin/hdfs dfs -mkdir -p input
$HADOOP_HOME/bin/hdfs dfs -put $HADOOP_HOME/etc/hadoop/* input
$HADOOP_HOME/bin/hadoop jar $HADOOP_HOME/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.9.2.jar grep input output 'dfs[a-z.]+'
$HADOOP_HOME/bin/hdfs dfs -get output
cp -r output /opt/bind/output