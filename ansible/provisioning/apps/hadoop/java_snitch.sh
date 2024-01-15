#!/usr/bin/env bash
#scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

BDWATCHDOG_PATH=/opt/BDWatchdog
JAVA_SNITCH_FILE=$BDWATCHDOG_PATH/MetricsFeeder/src/java_hadoop_snitch/java_snitch.py

tmux new -d -s "JAVA_SNITCH" "python3 $JAVA_SNITCH_FILE"
