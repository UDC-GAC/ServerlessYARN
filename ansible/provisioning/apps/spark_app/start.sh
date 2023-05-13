#!/usr/bin/env bash
cd "{{ bind_dir_on_container }}"

# Run JAR
start=`date +%s.%N`
$SPARK_HOME/bin/spark-submit \
  --class org.apache.spark.examples.SparkPi \
  --master yarn \
  --deploy-mode cluster \
  $SPARK_HOME/examples/jars/spark-examples_2.12-3.4.0.jar \
  1000
end=`date +%s.%N`
jar_runtime=$( echo "$end - $start" | bc -l )

# Store runtimes
echo Spark JAR runtime: $jar_runtime > runtime

