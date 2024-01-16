#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

INVENTORY=${scriptDir}/../../ansible.inventory

# This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
export PATH=$HOME/.local/bin:$PATH

echo ""
echo "Stopping all services..."
ansible-playbook ${scriptDir}/../stop_services_playbook.yml -i $INVENTORY -t stop_services
echo "Stop Done!"