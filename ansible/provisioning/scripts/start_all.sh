#!/usr/bin/env bash

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

INVENTORY=${scriptDir}/../../ansible.inventory

ansible-galaxy install gantsign.golang

if [ -n ${SLURM_JOB_ID} ]
then
    echo "Loading config from SLURM"
    python3 ${scriptDir}/load_config_from_slurm.py
    echo ""
    echo "Loading ansible inventory file"
    python3 ${scriptDir}/load_inventory_from_conf.py
fi

echo ""
echo "Installing necessary services and programs..."
ansible-playbook ${scriptDir}/../install_playbook.yml -i $INVENTORY
echo "Install Done!"

source /etc/environment

echo "Starting containers..."
ansible-playbook ${scriptDir}/../start_containers_playbook.yml -i $INVENTORY
echo "Containers started! "

echo "Launching services..."
ansible-playbook ${scriptDir}/../launch_playbook.yml -i $INVENTORY
echo "Launch Done!"
