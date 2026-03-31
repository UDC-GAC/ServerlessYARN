#!/bin/bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook manage_scaling_services.yml -i $INVENTORY -t enable_scaler
