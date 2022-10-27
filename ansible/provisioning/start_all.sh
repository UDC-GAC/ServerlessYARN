#!/usr/bin/env bash

INVENTORY=../ansible.inventory

#echo "Preparing ansible inventory"
#python3 load_inventory_from_conf.py $INVENTORY config/config.yml

ansible-galaxy install gantsign.golang

printf "\n"
echo "Installing necessary services and programs..."
ansible-playbook install_playbook.yml -i $INVENTORY
echo "Install Done!"

source /etc/environment

echo "Starting containers..."
ansible-playbook start_containers_playbook.yml -i $INVENTORY
echo "Containers started! "

echo "Launching services..."
ansible-playbook launch_playbook.yml -i $INVENTORY
echo "Launch Done!"
