#!/bin/bash

KERNEL_VERSION=5.4.233-1.el7.elrepo.x86_64
KERNEL_PACKAGE=kernel-lt-$KERNEL_VERSION.rpm
MIRROR_URL=https://mirrors.coreix.net/elrepo-archive-archive/kernel/el7/x86_64/RPMS/$KERNEL_PACKAGE

# Update yum mirrors
cat > /etc/yum.repos.d/CentOS-Base.repo <<'endmsg'
[base]
name=CentOS-$releasever - Base
baseurl=http://vault.centos.org/7.9.2009/os/$basearch/
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7

[updates]
name=CentOS-$releasever - Updates
baseurl=http://vault.centos.org/7.9.2009/updates/$basearch/
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7

[extras]
name=CentOS-$releasever - Extras
baseurl=http://vault.centos.org/7.9.2009/extras/$basearch/
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7

[centosplus]
name=CentOS-$releasever - Plus
baseurl=http://vault.centos.org/7.9.2009/centosplus/$basearch/
gpgcheck=1
enabled=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7
endmsg

# Update and install requirements
yum -y update
yum -y install yum-plugin-fastestmirror
yum -y install wget

# Download and install kernel
wget $MIRROR_URL
yum -y localinstall $KERNEL_PACKAGE
rm $KERNEL_PACKAGE

# Update grub
grub2-set-default 0
grub2-mkconfig -o /boot/grub2/grub.cfg