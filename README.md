# TFM

Prerequisites:
- BDWatchdog folder in ansible/provisioning/ with name "bdwatchdog"
- ServerlessContainer folder in ansible/provisioning/ with name "ServerlessContainers"

When using vagrant to deploy virtual cluster:
- You must ensure "id_rsa.pub" doesn't exist when executing "vagrant up" the first time (or after a "vagrant destroy")

Execution of playbooks example:
- ansible-playbook /vagrant/ansible/provisioning/install_playbook.yml
- ansible-playbook /vagrant/ansible/provisioning/launch_playbook.yml
- ansible-playbook /vagrant/ansible/provisioning/lxd_containers_playbook.yml

