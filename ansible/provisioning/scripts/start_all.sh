#!/usr/bin/env bash
set -e

## Main variables
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
INVENTORY=${scriptDir}/../../ansible.inventory

print_usage ()
{
    echo "Usage: $arg0 [-h --> print usage for help] \\"
    echo "       $blnk [-s --> skip inventory load]"
}

## Script flags
load_inventory_flag='true'

while getopts 'sh' flag; do
  case "${flag}" in
    s) load_inventory_flag='false' ;;
    h) print_usage
       exit 0 ;;
    *) print_usage
       exit 1 ;;
  esac
done

## Script functions
check_files_to_template ()
{
    echo "Checking required files..."

    config_modules_path="${scriptDir}/../config/modules"
    config_modules="
        ${config_modules_path}/01-general.yml \
        ${config_modules_path}/02-hosts.yml \
        ${config_modules_path}/03-services.yml \ 
        ${config_modules_path}/04-disk.yml \
        ${config_modules_path}/05-power.yml \
        ${config_modules_path}/06-hdfs.yml \
        ${config_modules_path}/07-containers.yml \
        ${config_modules_path}/08-apps.yml \
    "

    FILES_TO_TEMPLATE="$INVENTORY $config_modules"

    for file in $FILES_TO_TEMPLATE
    do
        if [ ! -f $file ]; then
            echo "$(realpath -s --relative-to=$PWD $file) does not exists, a copy of $(realpath -s --relative-to=$PWD $file.template) will be created instead"
            cp $file.template $file
        fi
    done
}

setup_config ()
{
    # This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
    export PATH=$HOME/.local/bin:$PATH

    ## Install required ansible collections
    echo ""
    ansible-galaxy collection install ansible.posix:==1.5.0

    echo "Load platform configuration from modules..."
    ansible-playbook ${scriptDir}/../load_config_playbook.yml -i $INVENTORY
    echo "Configuration loaded!"

    # Check if we are in a SLURM environment
    if [ ! -z ${SLURM_JOB_ID} ]
    then
        echo ""
        echo "Downloading required packages for scripts"
        pip3 install -r ${scriptDir}/requirements.txt
        echo "Loading config from SLURM"
        python3 ${scriptDir}/load_config_from_slurm.py
    fi
}

load_inventory_file ()
{
    echo ""
    echo "Loading ansible inventory file"
    python3 ${scriptDir}/load_inventory_from_conf.py
}

run_ansible_playbooks ()
{
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
}

## Script execution
# Copy ansible.cfg to $HOME
cp ${scriptDir}/../../ansible.cfg ~/.ansible.cfg

check_files_to_template

setup_config

# Check if load inventory flag is enabled
if [ "$load_inventory_flag" = true ]
then
    load_inventory_file
fi

run_ansible_playbooks