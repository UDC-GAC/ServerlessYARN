#!/usr/bin/env bash
set -e

## Main variables
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
INVENTORY=${scriptDir}/../../ansible.inventory
FILES_TO_TEMPLATE="$INVENTORY ${scriptDir}/../config/config.yml"

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
    for file in $FILES_TO_TEMPLATE
    do
        if [ ! -f $file ]; then
            echo "$(realpath -s --relative-to=$PWD $file) does not exists, a copy of $(realpath -s --relative-to=$PWD $file.template) will be created instead"
            cp $file.template $file
        fi
    done
}

setup_slurm_config ()
{
    echo ""
    echo "Downloading required packages for scripts"
    pip3 install -r ${scriptDir}/requirements.txt
    echo "Loading config from SLURM"
    python3 ${scriptDir}/load_config_from_slurm.py
}

load_inventory_file ()
{
    echo ""
    echo "Loading ansible inventory file"
    python3 ${scriptDir}/load_inventory_from_conf.py
}

run_ansible_playbooks ()
{
    # This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
    export PATH=$HOME/.local/bin:$PATH

    ## Install required ansible collections
    echo ""
    ansible-galaxy collection install ansible.posix:==1.5.0

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

# Check if we are in a SLURM environment
if [ ! -z ${SLURM_JOB_ID} ]
then
    setup_slurm_config
fi

# Check if load inventory flag is enabled
if [ "$load_inventory_flag" = true ]
then
    load_inventory_file
fi

run_ansible_playbooks