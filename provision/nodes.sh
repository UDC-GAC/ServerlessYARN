#!/bin/bash

apt-get -y update
apt-get -y install python-setuptools wget curl sshpass vim nano

# Copy ssh public key
USER_DIR=/home/vagrant/.ssh
sed -i '1!d' $USER_DIR/authorized_keys >& /dev/null
cat /vagrant/id_rsa.pub >> $USER_DIR/authorized_keys
chown vagrant:vagrant $USER_DIR/authorized_keys
chmod 0600 $USER_DIR/authorized_keys >& /dev/null

