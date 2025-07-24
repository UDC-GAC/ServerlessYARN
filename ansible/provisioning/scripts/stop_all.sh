#!/usr/bin/env bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
INVENTORY=${scriptDir}/../../ansible.inventory

print_usage ()
{
    echo "Usage: $arg0 [-h --> print usage for help] \\"
    echo "       $blnk [-l --> clean logs] \\"
    echo "       $blnk [-r --> remove logical volumes] \\"
    echo "       $blnk [-s --> dont stop services] \\"
    echo "       $blnk [-o --> dont stop opentsdb]"
}

## Script flags
clean_logs_flag='false'
remove_lv_flag='false'
stop_services_flag='true'
stop_opentsdb_flag='false'

while getopts 'lrsoh' flag; do
  case "${flag}" in
    l) clean_logs_flag='true' ;;
    r) remove_lv_flag='true' ;;
    s) stop_services_flag='false' ;;
    o) stop_opentsdb_flag='true' ;;
    h) print_usage
       exit 0 ;;
    *) print_usage
       exit 1 ;;
  esac
done

setup_config ()
{
    # This is useful in case we need to use a newer version of ansible installed in $HOME/.local/bin
    export PATH=$HOME/.local/bin:$PATH
}

remove_lv ()
{
    echo ""
    echo "Removing logical volumes..."
    ansible-playbook ${scriptDir}/../install_playbook.yml -i $INVENTORY -t remove_lv
    echo "Logical Volumes deleted!"
}

stop_services ()
{
    echo ""
    echo "Stopping all services..."
    ansible-playbook ${scriptDir}/../stop_services_playbook.yml -i $INVENTORY -t stop_services
    echo "Stop Done!"
}

stop_opentsdb ()
{
    echo ""
    echo "Stopping OpenTSDB..."
    ansible-playbook ${scriptDir}/../stop_services_playbook.yml -i $INVENTORY -t stop_opentsdb
    echo "Stop Done!"
}

clean_logs ()
{
    echo ""
    echo "Cleaning all logs..."
    ansible-playbook ${scriptDir}/../stop_services_playbook.yml -i $INVENTORY -t clean_logs
    echo "Log clean Done!"
}

## Script execution
setup_config

if [ "$remove_lv_flag" = true ]
then
    remove_lv
fi

if [ "$stop_services_flag" = true ]
then
    stop_services
fi

if [ "$stop_opentsdb_flag" = true ]
then
    stop_opentsdb
fi

if [ "$clean_logs_flag" = true ]
then
    clean_logs
fi