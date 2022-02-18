#!/bin/bash

apt-get -y update
apt-get -y install python-setuptools wget curl sshpass vim nano

#if [ ! -f /etc/pki/rpm-gpg/RPM-GPG-KEY-remi ]; then
#	wget http://rpms.famillecollet.com/RPM-GPG-KEY-remi -O /etc/pki/rpm-gpg/RPM-GPG-KEY-remi
#fi

#if [ ! -f remi-release-7.rpm ]; then
#	wget http://rpms.remirepo.net/enterprise/remi-release-7.rpm
#fi

#rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-remi
#yum -y localinstall remi-release-7.rpm

# Copy ssh public key
USER_DIR=/home/vagrant/.ssh
sed -i '1!d' $USER_DIR/authorized_keys >& /dev/null
cat /vagrant/id_rsa.pub >> $USER_DIR/authorized_keys
chown vagrant:vagrant $USER_DIR/authorized_keys
chmod 0600 $USER_DIR/authorized_keys >& /dev/null

