#!/bin/bash

# Install ansible and other stuff
apt-get -y update
apt-get -y install python-setuptools wget curl sshpass vim nano ansible
mkdir -p /etc/ansible
cp /vagrant/ansible/ansible.cfg /etc/ansible
cp /vagrant/ansible/ansible.inventory /etc/ansible/hosts

# Create ssh keys
USER_DIR=/home/vagrant/.ssh

if [ ! -f /vagrant/id_rsa.pub ]; then
	echo -e 'y\n' | sudo -u vagrant ssh-keygen -t rsa -f $USER_DIR/id_rsa -q -N ''
	chown vagrant:vagrant $USER_DIR/id_rsa*
	cp $USER_DIR/id_rsa.pub /vagrant    
fi
