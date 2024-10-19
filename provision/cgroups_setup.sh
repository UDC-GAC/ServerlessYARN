#!/bin/bash

CGROUPS_VERSION=$1

if [ "$CGROUPS_VERSION" = v1 ];
then
    sed -i 's/GRUB_CMDLINE_LINUX="[^"]*/& systemd.unified_cgroup_hierarchy=0/' /etc/default/grub
elif [ "$CGROUPS_VERSION" = v2 ];
then
    sed -i 's/GRUB_CMDLINE_LINUX="[^"]*/& systemd.unified_cgroup_hierarchy=1/' /etc/default/grub
else
    echo "ERROR: Cgroups version must be v1 or v2"
    exit 1
fi

update-grub