#!/bin/bash
set -e
APP_DIR=$1
FILES_DIR=$2
INSTALL_SCRIPT=$3

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -t create_app \
   --extra-vars \
       "app_dir=$APP_DIR \
       files_dir=$FILES_DIR \
       install_script=$INSTALL_SCRIPT"
