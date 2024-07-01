#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

source ${scriptDir}/files_dir/app_config.sh

# Check if stress is available
path_to_executable=$(which stress)
if [ -x "$path_to_executable" ] ; then
    echo "$path_to_executable available"
    ${path_to_executable} --cpu $CORES_TO_STRESS --timeout $TIMEOUT_SECONDS
else
    echo "Stress not available, using simple stresser..."
    seq $CORES_TO_STRESS | xargs -P0 -n1 timeout $TIMEOUT_SECONDS md5sum /dev/zero
fi

exit_code=$?

if [ $exit_code -ne 123 ]; then
    exit $exit_code
else
    exit 0
fi
