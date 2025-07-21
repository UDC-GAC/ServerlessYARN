#!/usr/bin/env bash
## Optional file if you need to install some packages on the containers

apt-get -y update

if [ -d /opt/{{ app_dir | basename }}/{{ install_files | basename  }} ] && [ -f /opt/{{ app_dir | basename }}/{{ install_files | basename  }}/package_config.sh ];
then
    # Install other package
    source /opt/{{ app_dir | basename }}/{{ install_files | basename }}/package_config.sh
    if [ $INSTALL_STRESS_NG = 1 ];
    then
        apt-get -y install stress-ng
    fi
else
    # Install stress
    apt-get -y install stress
fi