#!/bin/bash
set -e

scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
cd $scriptDir/../../../../
INVENTORY=../ansible.inventory
