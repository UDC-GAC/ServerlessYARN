#!/bin/bash
set -e

cd ../../
INVENTORY=../ansible.inventory

unbuffer ansible-playbook launch_playbook.yml -i $INVENTORY -t disable_scaler
