#!/usr/bin/env bash
hadoop_add_profile tools

function _tools_hadoop_classpath
{
  hadoop_add_classpath "${HADOOP_HOME}/share/hadoop/tools/lib/*"
}
