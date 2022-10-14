#!/usr/bin/env bash

#INVENTORY=/etc/ansible/hosts
INVENTORY=../ansible.inventory

#echo "Preparing ansible inventory"
#python3 load_inventory_from_conf.py $INVENTORY config/config.yml

printf "\n"
echo "Installing necessary services and programs..."
ansible-playbook install_playbook.yml -i $INVENTORY
echo "Install Done!"

echo "Starting LXC containers..."
ansible-playbook lxd_containers_playbook.yml -i $INVENTORY
echo "Containers started! "

echo "Launching services..."
ansible-playbook launch_playbook.yml -i $INVENTORY
echo "Launch Done!"
