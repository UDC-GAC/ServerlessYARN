#!/usr/bin/env bash
cd {{ bind_dir_on_container }}
set -e

OUTPUT_DIR="{{ bind_dir_on_container }}/{{ output_dir }}"

output_file="$OUTPUT_DIR/output_spark_app_`date +%H-%M-%S`"
app_log_file="$OUTPUT_DIR/app_log_spark_app_`date +%H-%M-%S`"
runtime_file="$OUTPUT_DIR/runtime_spark_app_`date +%H-%M-%S`"

# Run JAR
start=`date +%s.%N`
$SPARK_HOME/bin/spark-submit \
  --class org.apache.spark.examples.SparkPi \
  --master yarn \
  --deploy-mode client \
  $SPARK_HOME/examples/jars/spark-examples_2.12-{{ spark_version }}.jar \
  1000 2> $app_log_file 1>$output_file

end=`date +%s.%N`
jar_runtime=$( echo "$end - $start" | bc -l )

# Store runtimes
echo Spark JAR runtime: $jar_runtime > $runtime_file

