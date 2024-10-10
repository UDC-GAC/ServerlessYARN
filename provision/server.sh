#!/bin/bash

# Install basic stuff
apt-get -y update
apt-get -y install python-setuptools wget curl sshpass vim nano

## Apt install ansible
apt-get install -y software-properties-common
add-apt-repository --yes --update ppa:ansible/ansible
apt-get -y update
apt-get install -y ansible

mkdir -p /etc/ansible
cp /vagrant/ansible/ansible.cfg /etc/ansible

# Create ssh keys
USER_DIR=/home/vagrant/.ssh
echo -e 'y\n' | sudo -u vagrant ssh-keygen -t rsa -f $USER_DIR/id_rsa -q -N ''
chown vagrant:vagrant $USER_DIR/id_rsa*
cp $USER_DIR/id_rsa.pub /vagrant/provision
sed -i '1!d' $USER_DIR/authorized_keys >& /dev/null
cat /vagrant/provision/id_rsa.pub >> $USER_DIR/authorized_keys
chown vagrant:vagrant $USER_DIR/authorized_keys
chmod 0600 $USER_DIR/authorized_keys >& /dev/null

# Disable strict host key checking
if [ ! -f /etc/ssh/ssh_config.d/01-stricthostkey.con ]; then
cat > /etc/ssh/ssh_config.d/01-stricthostkey.conf << EOF
Host *
    StrictHostKeyChecking no
EOF
fi
