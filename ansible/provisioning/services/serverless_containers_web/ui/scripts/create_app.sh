#!/bin/bash
set -e
APP_NAME=$1

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source $scriptDir/access_playbooks_dir.sh

#unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -t create_app \
#    --extra-vars \
#        "template_definition_file=app_container.def \
#        definition_file=$DEFINITION_FILE \
#        image_file=$IMAGE_FILE \
#        app_name=$APP_NAME \
#        files_dir=$FILES_DIR \
#        install_script=$INSTALL_SCRIPT"

unbuffer ansible-playbook start_containers_playbook.yml -i $INVENTORY -t create_app \
    --extra-vars "app_name=$APP_NAME"