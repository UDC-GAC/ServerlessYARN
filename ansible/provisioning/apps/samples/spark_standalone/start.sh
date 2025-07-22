#!/usr/bin/env bash
cd {{ bind_dir_on_container }}

#exit 1 # uncomment if you want the app to fail to execute it yourself from inside the container

OUTPUT_DIR="{{ bind_dir_on_container }}/{{ output_dir }}"

export SPARK_HOME=/opt/spark

output_file="$OUTPUT_DIR/output_spark_standalone_`date +%d-%m-%y--%H-%M-%S`"
app_log_file="$OUTPUT_DIR/app_log_spark_standalone_`date +%d-%m-%y--%H-%M-%S`"
runtime_file="$OUTPUT_DIR/runtime_spark_standalone_`date +%d-%m-%y--%H-%M-%S`"

# Run JAR
start=`date +%s.%N`

$SPARK_HOME/bin/spark-submit \
  --class org.apache.spark.examples.SparkPi \
  --master local[*] \
  --deploy-mode client \
  $SPARK_HOME/examples/jars/spark-examples_2.12-{{ spark_version }}.jar \
  1000 2> $app_log_file 1>$output_file

end=`date +%s.%N`
runtime=$( echo "$end - $start" | bc -l )

# Store runtime
echo Spark standalone app runtime: $runtime > $runtime_file
