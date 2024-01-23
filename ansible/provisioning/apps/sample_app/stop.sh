#!/usr/bin/env bash

# Check if stress is available
path_to_executable=$(which stress)
if [ -x "$path_to_executable" ] ; then
    echo "Stopping $path_to_executable..."
    command_to_stop=stress
else
    echo "Stress not available, stopping simple stresser..."
    command_to_stop=md5sum
fi

pkill -9 -f $command_to_stop
exit_code=$?

if [ $exit_code -gt 1 ]; then
    exit $exit_code
else
    exit 0
fi
