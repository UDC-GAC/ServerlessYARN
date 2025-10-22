#!/bin/bash

SERVER_HOSTNAME=$1

# Copy all ssh public keys (excluding self and server, as they should already be ready)
USER_DIR=/home/vagrant/.ssh
shopt -s extglob
cat /vagrant/provision/id_rsa_!(*`hostname`|$SERVER_HOSTNAME).pub >> $USER_DIR/authorized_keys || true
