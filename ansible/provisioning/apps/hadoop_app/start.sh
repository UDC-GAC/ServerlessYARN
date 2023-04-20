#!/usr/bin/env bash
cd "{{ bind_dir_on_container }}"
# Remove previous output from local file system if exists
rm -rf output

# Store data in HDFS
start=`date +%s.%N`
$HADOOP_HOME/bin/hdfs dfs -mkdir -p input
$HADOOP_HOME/bin/hdfs dfs -put $HADOOP_HOME/etc/hadoop/* input
end=`date +%s.%N`
hdfs_put_time=$( echo "$end - $start" | bc -l )

# Run JAR
start=`date +%s.%N`
$HADOOP_HOME/bin/hadoop jar $HADOOP_HOME/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.9.2.jar grep input output 'dfs[a-z.]+'
end=`date +%s.%N`
jar_runtime=$( echo "$end - $start" | bc -l )

# Get output from HDFS
start=`date +%s.%N`
$HADOOP_HOME/bin/hdfs dfs -get output
end=`date +%s.%N`
hdfs_put_time=$(echo $hdfs_put_time + $( echo "$end - $start" | bc -l ) | bc -l)

# Store runtimes
echo HDFS time: $hdfs_put_time > runtime
echo JAR runtime: $jar_runtime >> runtime
echo Total time: $(echo $hdfs_put_time + $jar_runtime | bc -l) >> runtime

# Move results to bind dir
# cp -r output /opt/bind/
# mv -f runtime /opt/bind/