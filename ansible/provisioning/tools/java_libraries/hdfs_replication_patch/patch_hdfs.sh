#!/bin/bash

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

HADOOP_VERSION="3.4.2"
HADOOP_HOME="/home/vagrant/hadoop/hadoop-${HADOOP_VERSION}-src"

echo "This script requires an existing hadoop source directory, assuming ${HADOOP_HOME} and version ${HADOOP_VERSION}..."
if [ ! -d "$HADOOP_HOME" ]; then
    echo "ERROR, $HADOOP_HOME does not exist!"
    exit 1
fi

CLIENT_PATH="${HADOOP_HOME}/hadoop-hdfs-project/hadoop-hdfs-client/src/main/java/org/apache/hadoop/hdfs"
NN_PATH="${HADOOP_HOME}/hadoop-hdfs-project/hadoop-hdfs/src/main/java/org/apache/hadoop/hdfs/server/namenode"

for i in "NameNodeProxiesClient.java ${CLIENT_PATH}" "ClientNamenodeProtocolTranslatorPB.java ${CLIENT_PATH}/protocolPB" "FSNamesystem.java ${NN_PATH}"; do

    a=( $i )

    file="${a[0]}"
    dest="${a[1]}"

    echo "Copying ${file} into ${dest}..."
    cp ${scriptDir}/${file} ${dest}

done

echo "Compiling..."
cd $HADOOP_HOME
mvn install -pl hadoop-hdfs-project/hadoop-hdfs,hadoop-hdfs-project/hadoop-hdfs-client -am -DskipTests -Dmaven.javadoc.skip=true -Dcheckstyle.skip=true -Dspotbugs.skip=true

echo "Recovering new JAR file..."
cp $HADOOP_HOME/hadoop-hdfs-project/hadoop-hdfs/target/hadoop-hdfs-${HADOOP_VERSION}.jar ${scriptDir}/../../../apps/base/hadoop_app/
cp $HADOOP_HOME/hadoop-hdfs-project/hadoop-hdfs-client/target/hadoop-hdfs-client-${HADOOP_VERSION}.jar ${scriptDir}/../../../apps/base/hadoop_app/
