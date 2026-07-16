#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source ${scriptDir}/set_env.sh

# This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
export PATH=$HOME/.local/bin:$PATH

echo ""
echo "Stopping all containers..."
ansible-playbook ${PLAYBOOK_DIR}/stop_containers_playbook.yml -i $ANSIBLE_INVENTORY
echo "Stop Done!"