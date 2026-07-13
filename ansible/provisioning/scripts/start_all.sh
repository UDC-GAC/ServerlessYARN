#!/usr/bin/env bash
set -e

## Main variables
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
PROVISION_DIR=$( realpath ${scriptDir}/.. )
SCRIPTS_DIR=${PROVISION_DIR}/scripts
INVENTORY=${PROVISION_DIR}/../ansible.inventory.yml

CONFIG_MODULE_PATH="${PROVISION_DIR}/config/modules"
CONFIG_MODULE_LIST=(
    01-general.yml \
    02-hosts.yml \
    03-services.yml \
    04-disk.yml \
    05-power.yml \
    06-hdfs.yml \
    07-containers.yml \
    08-apps.yml \
    09-plugins.yml \
)

## Colors used to print
LIGHT_CYAN="\e[38;5;81m"
RESET="\e[0m"
BANNER_COLOR=${LIGHT_CYAN}

print_usage ()
{
    echo "Usage: $arg0 [-h --> print usage for help] \\"
    echo "       $blnk [-s --> skip inventory load]  \\"
    echo "       $blnk [-d --> reset disks]" # reset disks in order to re-benchmark their performance (requires not skipping inventory load)
}

## Script flags
load_inventory_flag='true'
reset_disks_flag='false'

while getopts 'shd' flag; do
  case "${flag}" in
    s) load_inventory_flag='false' ;;
    d) reset_disks_flag='true' ;;
    h) print_usage
       exit 0 ;;
    *) print_usage
       exit 1 ;;
  esac
done

## Script functions
print_banner () {
    local msg="* [ServerlessYARN INFO] $1 *"
    local edge=$(echo "$msg" | sed 's/./*/g')

    printf "${BANNER_COLOR}\n%s\n%s\n%s${RESET}\n" "$edge" "$msg" "$edge"
}

install_prerequisites ()
{
    print_banner "Installing prerequisites"

    # This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
    export PATH=$HOME/.local/bin:$PATH

    ## Install required ansible collections
    ansible-galaxy collection install ansible.posix:==1.5.0

    echo -e "\nDownloading required packages for scripts"
    pip3 install -r ${SCRIPTS_DIR}/requirements.txt

    # Install custom python utilities
    pip3 install --editable ${PROVISION_DIR}/python_utils/ ## 'editable' mode allows changes to be automatically reflected without re-installing

}

check_files_to_template ()
{
    print_banner "Checking required files"

    config_modules=("${CONFIG_MODULE_LIST[@]/#/$CONFIG_MODULE_PATH/}") ## this adds the prefix '$CONFIG_MODULE_PATH/' to every item in list

    FILES_TO_TEMPLATE="$INVENTORY ${config_modules[@]}"

    for file in $FILES_TO_TEMPLATE
    do
        if [ ! -f $file ]; then
            filename=$(basename $file)
            file_directory=$(realpath $(dirname $file))
            template_file=$file_directory/template.$filename

            echo "$(realpath -s --relative-to=$PWD $file) does not exists, a copy of $(realpath -s --relative-to=$PWD $template_file) will be created instead"
            cp $template_file $file
        fi
    done
}

setup_config ()
{
    print_banner "Setting configuration"

    # Check if new parameters have been added to config templates (e.g., new update via git pull)
    for filename in "${CONFIG_MODULE_LIST[@]}"
    do
        python3 ${SCRIPTS_DIR}/config/sync_yaml_config.py --template ${CONFIG_MODULE_PATH}/template.$filename --config ${CONFIG_MODULE_PATH}/$filename
    done

    # Check if we are in a SLURM environment
    if [ ! -z ${SLURM_JOB_ID} ]
    then
        echo "Loading config from SLURM"
        python3 ${SCRIPTS_DIR}/config/load_config_from_slurm.py
    fi

    echo "Load platform configuration from modules"
    ansible-playbook ${PROVISION_DIR}/load_config_playbook.yml -i $INVENTORY
    echo "Configuration loaded!"

}

load_inventory_file ()
{
    print_banner "Loading ansible inventory file"

    if [ "$reset_disks_flag" = false ]
    then
        python3 ${SCRIPTS_DIR}/config/load_inventory_from_conf.py
    else
        python3 ${SCRIPTS_DIR}/config/load_inventory_from_conf.py "reset_disks"
    fi
}

run_ansible_playbooks ()
{
    print_banner "Installing necessary services and programs"
    ansible-playbook ${PROVISION_DIR}/install_playbook.yml -i $INVENTORY
    echo "Install Done!"

    source /etc/environment
    # Repeat the export command in case the /etc/environment file overwrites the PATH variable
    export PATH=$HOME/.local/bin:$PATH

    print_banner "Starting containers"
    ansible-playbook ${PROVISION_DIR}/start_containers_playbook.yml -i $INVENTORY
    echo "Containers started!"

    print_banner "Launching services"
    ansible-playbook ${PROVISION_DIR}/launch_playbook.yml -i $INVENTORY
    echo "Launch Done!"

    print_banner "Loading applications"
    python3 ${SCRIPTS_DIR}/load_apps_from_config.py
    echo "Apps loaded!"
}

######################## Script execution ########################
install_prerequisites

check_files_to_template

setup_config

# Check if load inventory flag is enabled
if [ "$load_inventory_flag" = true ]
then
    load_inventory_file
fi

run_ansible_playbooks