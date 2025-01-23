#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

INVENTORY=${scriptDir}/../../ansible.inventory

# This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
export PATH=$HOME/.local/bin:$PATH

echo ""
echo "Restarting services..."
ansible-playbook ${scriptDir}/../install_playbook.yml -i $INVENTORY -t restart_services
ansible-playbook ${scriptDir}/../start_containers_playbook.yml -i $INVENTORY -t restart_services
ansible-playbook ${scriptDir}/../launch_playbook.yml -i $INVENTORY -t restart_services
echo "Restart Done!"