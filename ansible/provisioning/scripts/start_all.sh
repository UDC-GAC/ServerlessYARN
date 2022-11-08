#!/usr/bin/env bash

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

INVENTORY=${scriptDir}/../../ansible.inventory

#echo "Preparing ansible inventory"
#python3 load_inventory_from_conf.py $INVENTORY config/config.yml

ansible-galaxy install gantsign.golang

printf "\n"
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
