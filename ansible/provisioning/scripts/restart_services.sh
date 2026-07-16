#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source ${scriptDir}/set_env.sh

# This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
export PATH=$HOME/.local/bin:$PATH

echo ""
echo "Restarting services..."
ansible-playbook ${PLAYBOOK_DIR}/install_playbook.yml -i $ANSIBLE_INVENTORY -t restart_services
ansible-playbook ${PLAYBOOK_DIR}/start_containers_playbook.yml -i $ANSIBLE_INVENTORY -t restart_services
ansible-playbook ${PLAYBOOK_DIR}/launch_playbook.yml -i $ANSIBLE_INVENTORY -t restart_services
echo "Restart Done!"