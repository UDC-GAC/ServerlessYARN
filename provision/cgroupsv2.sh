#!/bin/bash

sed -i 's/GRUB_CMDLINE_LINUX="[^"]*/& systemd.unified_cgroup_hierarchy=1/' /etc/default/grub
update-grub