#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

INVENTORY=${scriptDir}/../../ansible.inventory

## Copy ansible.cfg to $HOME
cp ${scriptDir}/../../ansible.cfg ~/.ansible.cfg

# This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
export PATH=$HOME/.local/bin:$PATH

## Install required ansible collections
ansible-galaxy collection install ansible.posix:==1.5.0

echo "Load platform configuration from modules..."
ansible-playbook ${scriptDir}/../load_config_playbook.yml -i $INVENTORY
echo "Configuration loaded!"

if [ ! -z ${SLURM_JOB_ID} ]
then
    echo "Downloading required packages for scripts"
    pip3 install -r ${scriptDir}/requirements.txt
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
# Repeat the export command in case the /etc/environment file overwrites the PATH variable
export PATH=$HOME/.local/bin:$PATH

echo "Starting containers..."
ansible-playbook ${scriptDir}/../start_containers_playbook.yml -i $INVENTORY
echo "Containers started! "

echo "Launching services..."
ansible-playbook ${scriptDir}/../launch_playbook.yml -i $INVENTORY
echo "Launch Done!"

echo "Load applications..."
python3 ${scriptDir}/load_apps_from_config.py
echo "Apps loaded!"