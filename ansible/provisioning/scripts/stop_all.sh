#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

INVENTORY=${scriptDir}/../../ansible.inventory

## If you want to remove or keep the logical volumes created (if any)
remove_lv=no

# This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
export PATH=$HOME/.local/bin:$PATH

echo ""
echo "Stopping all services..."
ansible-playbook ${scriptDir}/../stop_services_playbook.yml -i $INVENTORY -t stop_services
echo "Stop Done!"


if [ "$remove_lv" = yes ];
then
    echo ""
    echo "Removing logical volumes..."
    ansible-playbook ${scriptDir}/../install_playbook.yml -i $INVENTORY -t remove_lv
    echo "Logical Volumes deleted!"
fi
