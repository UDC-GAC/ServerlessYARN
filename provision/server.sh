#!/bin/bash

# Install basic stuff
apt-get -y update
apt-get -y install python-setuptools wget curl sshpass vim nano

## Apt install (broken for some reason)
#apt-get install -y software-properties-common
#add-apt-repository --yes --update ppa:ansible/ansible
#apt-get -y update
#apt-get install -y ansible

## Pip install ansible
apt-get install -y python3-pip
python3 -m pip install ansible

mkdir -p /etc/ansible
cp /vagrant/ansible/ansible.cfg /etc/ansible

# Create ssh keys
USER_DIR=/home/vagrant/.ssh

if [ ! -f /vagrant/id_rsa.pub ]; then
	echo -e 'y\n' | sudo -u vagrant ssh-keygen -t rsa -f $USER_DIR/id_rsa -q -N ''
	chown vagrant:vagrant $USER_DIR/id_rsa*
	cp $USER_DIR/id_rsa.pub /vagrant    
fi
