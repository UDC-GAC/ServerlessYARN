# TFM

Prerequisites:
- BDWatchdog folder in ansible/provisioning/ with name "bdwatchdog"
- ServerlessContainer folder in ansible/provisioning/ with name "ServerlessContainers"
- Vagrant and VirtualBox installed

When using vagrant to deploy virtual cluster:
- You must ensure "id_rsa.pub" doesn't exist when executing "vagrant up" the first time (or after a "vagrant destroy")

Workflow example:
- Change config properties of ansible/provisioning/config/config.yml
- On the directory with the Vagrantfile, start the virtual cluster with "vagrant up"
- Once done, log in into the server node with "vagrant ssh"
- Change directory to /vagrant/ansible/provisioning
- Execute "bash start_all.sh" to run all ansible playbooks
