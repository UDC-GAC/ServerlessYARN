#!/usr/bin/env bash
cd {{ bind_dir_on_container }}
set -e

# Store data in HDFS
start=`date +%s.%N`
$HADOOP_HOME/bin/hdfs dfs -mkdir -p input
$HADOOP_HOME/bin/hdfs dfs -put $HADOOP_HOME/etc/hadoop/* input
$HADOOP_HOME/bin/hdfs dfs -rm -r input/shellprofile.d
end=`date +%s.%N`
hdfs_put_time=$( echo "$end - $start" | bc -l )

# Run JAR
start=`date +%s.%N`
$HADOOP_HOME/bin/hadoop jar $HADOOP_HOME/share/hadoop/mapreduce/hadoop-mapreduce-examples-{{ hadoop_version }}.jar grep input output 'dfs[a-z.]+'

## Generate mock results (to test uploading data from local HDFS to global one)
touch $HOME/output_data
echo "TEST for upload data from local HDFS to hlobal one" >> $HOME/output_data
$HADOOP_HOME/bin/hdfs dfs -put $HOME/output_data

end=`date +%s.%N`
jar_runtime=$( echo "$end - $start" | bc -l )

output_file="output_hadoop_app_`date +%H-%M-%S`"
runtime_file="runtime_hadoop_app_`date +%H-%M-%S`"

# Get output from HDFS
start=`date +%s.%N`
$HADOOP_HOME/bin/hdfs dfs -get output
mv output $output_file
end=`date +%s.%N`
hdfs_put_time=$(echo $hdfs_put_time + $( echo "$end - $start" | bc -l ) | bc -l)

# Store runtimes
echo HDFS time: $hdfs_put_time > $runtime_file
echo JAR runtime: $jar_runtime >> $runtime_file
echo Total time: $(echo $hdfs_put_time + $jar_runtime | bc -l) >> $runtime_file

# Move results to bind dir
# cp -r output /opt/bind/
# mv -f runtime /opt/bind/