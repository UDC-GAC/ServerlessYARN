#!/bin/bash

echo "Run mvn clean package"
mvn clean package

echo "Copy target JAR file into ../../../apps/base/global_hdfs/runtime_files/"
cp target/simple-distcp-1.0.jar ../../../apps/base/global_hdfs/runtime_files/simple-distcp.jar