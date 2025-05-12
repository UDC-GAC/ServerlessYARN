#!/bin/bash
set -e
HOST_NAMES=$1
NEW_DISKS=$2
EXTRA_DISK=$3
MEASURE_HOST_LIST=$4
THROTTLE_CONTAINERS_BW=$5

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

# We disable services that may generate scaling requests and cap bandwidth of running containers to speed up the extension process
if [ $THROTTLE_CONTAINERS_BW == 1 ];
then
    unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t disable_scaling_services,limit_containers_bw \
        --extra-vars \
            "host_list=$HOST_NAMES"
fi

unbuffer ansible-playbook install_playbook.yml -i $INVENTORY -t extend_lv -l $HOST_NAMES \
    --extra-vars \
        "new_disks_list=$NEW_DISKS \
        extra_disk=$EXTRA_DISK \
        measure_host_list_str=$MEASURE_HOST_LIST"

unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t extend_lv \
    --extra-vars \
        "host_list=$HOST_NAMES"

# Re-enable disabled services
if [ $THROTTLE_CONTAINERS_BW == 1 ];
then
    unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t enable_scaling_services
fi