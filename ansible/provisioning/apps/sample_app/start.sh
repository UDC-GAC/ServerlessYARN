#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

source ${scriptDir}/{{ runtime_files }}/app_config.sh

OUTPUT_DIR="{{ bind_dir_on_container }}/{{ output_dir }}"
#mkdir -p $OUTPUT_DIR # --> it is not necessary to create it, it will be done by an Ansible task

stress_ng_executable=$(which stress-ng)
stress_executable=$(which stress)

# Check if stress-ng is available
if [ -x "$stress_ng_executable" ] ; then
    echo "$stress_ng_executable available"
    echo "Using `stress-ng --version`" >> $OUTPUT_DIR/stress_ng_output.txt
    ${stress_ng_executable} --cpu $CORES_TO_STRESS --timeout $TIMEOUT_SECONDS &>> $OUTPUT_DIR/stress_ng_output.txt

# Check if stress is available
elif [ -x "$stress_executable" ] ; then
    echo "$stress_executable available"
    echo "Using `stress --version` version" >> $OUTPUT_DIR/stress_output.txt
    ${stress_executable} --cpu $CORES_TO_STRESS --timeout $TIMEOUT_SECONDS >> $OUTPUT_DIR/stress_output.txt

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
