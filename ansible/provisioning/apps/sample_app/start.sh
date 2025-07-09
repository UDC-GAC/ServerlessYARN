#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

source ${scriptDir}/{{ runtime_files }}/app_config.sh

OUTPUT_DIR="{{ bind_dir_on_container }}/{{ output_dir }}"
mkdir $OUTPUT_DIR

# Check if stress is available
path_to_executable=$(which stress)
if [ -x "$path_to_executable" ] ; then
    echo "$path_to_executable available"
    ${path_to_executable} --cpu $CORES_TO_STRESS --timeout $TIMEOUT_SECONDS >> $OUTPUT_DIR/stress_output.txt
else
    echo "Stress not available, using simple stressor..."
    (time seq $CORES_TO_STRESS | xargs -P0 -n1 timeout $TIMEOUT_SECONDS md5sum /dev/zero) &>> $OUTPUT_DIR/simple_stressor.txt
fi

exit_code=$?

if [ $exit_code -ne 123 ]; then
    exit $exit_code
else
    exit 0
fi
