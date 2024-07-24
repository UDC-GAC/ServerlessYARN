#!/usr/bin/env bash

## Run SSH server
/usr/sbin/sshd

## Setup passwordless ssh
ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 0600 ~/.ssh/authorized_keys
ssh-keyscan -t rsa localhost >> ~/.ssh/known_hosts
ssh-keyscan -t rsa 0.0.0.0 >> ~/.ssh/known_hosts
ssh-keyscan -t rsa `hostname` >> ~/.ssh/known_hosts