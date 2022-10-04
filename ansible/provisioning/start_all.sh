#!/usr/bin/env bash

echo "Preparing ansible inventory"
sudo python3 load_inventory_from_conf.py /etc/ansible/hosts config/config.yml

printf "\n"
echo "Installing necessary services and programs..."
ansible-playbook install_playbook.yml
echo "Install Done!"

echo "Starting LXC containers..."
ansible-playbook lxd_containers_playbook.yml
echo "Containers started! "

echo "Launching services..."
ansible-playbook launch_playbook.yml
echo "Launch Done!"
