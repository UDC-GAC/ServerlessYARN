#!/bin/bash

SERVER_HOSTNAME=$1

apt-get -y update
apt-get -y install python-setuptools wget curl sshpass vim nano

# Create ssh keys
USER_DIR=/home/vagrant/.ssh
echo -e 'y\n' | sudo -u vagrant ssh-keygen -t rsa -f $USER_DIR/id_rsa -q -N ''
chown vagrant:vagrant $USER_DIR/id_rsa*
cp $USER_DIR/id_rsa.pub /vagrant/provision/id_rsa_`hostname`.pub
sed -i '1!d' $USER_DIR/authorized_keys >& /dev/null
cat /vagrant/provision/id_rsa_`hostname`.pub >> $USER_DIR/authorized_keys
chown vagrant:vagrant $USER_DIR/authorized_keys
chmod 0600 $USER_DIR/authorized_keys >& /dev/null

# Copy server ssh public key
cat /vagrant/provision/id_rsa_$SERVER_HOSTNAME.pub >> $USER_DIR/authorized_keys

# Disable strict host key checking
if [ ! -f /etc/ssh/ssh_config.d/01-stricthostkey.con ]; then
cat > /etc/ssh/ssh_config.d/01-stricthostkey.conf << EOF
Host *
    StrictHostKeyChecking no
EOF
fi