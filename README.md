# AutoServerlessWeb

This project provides a web platform for the framework ServerlessContainers which can be found on its own [web page](http://bdwatchdog.dec.udc.es/serverless/index.html). 

ServerlessContainers implements a serverless environment that supports LXC containers, managing their resources following several policies to fit them according to the usage in real time.

This platform provides an automatic way of deploying ServerlessContainers through IaC tools such as Vagrant and Ansible, as well as a web interface to interact easily with the framework and manage basic aspects of it.

## Getting Started

### Prerequisites
- Vagrant
- VirtualBox
- Vagrant plugins: vagrant-hostmanager, vagrant-reload

> vagrant-reload plugin is only necessary when deploying nodes with cgroups V2

You may install the vagrant plugins with the following commands:
    ```
    vagrant plugin install vagrant-hostmanager
    vagrant plugin install vagrant-reload
    ```

### Quickstart
- You can clone this repository with
    ```
    git clone https://github.com/UDC-GAC/AutoServerlessWeb.git
    ```

- Once cloned, change directory to ansible/provisioning 
    ```
    cd AutoServerlessWeb/ansible/provisioning
    ```

- And clone both BDWatchdog (with name "bdwatchdog") and ServerlessContainers (with name "ServerlessContainers") in that directory

    ```
    git clone https://github.com/UDC-GAC/bdwatchdog.git
    git clone https://github.com/UDC-GAC/ServerlessContainers.git
    ```

- Modify **config/config.yml** to customize your environment.

- Go back to the root directory of the repository and deploy the virtual cluster with vagrant:
    ```
    cd ../../
    vagrant up
    ```

**NOTE**: You must ensure **"id_rsa.pub"** doesn't exist when executing "vagrant up" the first time (or after a "vagrant destroy")

- Log into the server node and execute the script to install all the necessary stuff for the framework, start the desired containers and start the ServerlessContainers services:
    ```
    vagrant ssh
    cd /vagrant/ansible/provisioning/scripts
    python3 load_inventory_from_conf.py
    bash start_all.sh
    ```

- Once you are done, you can shutdown the cluster exiting the server node and executing:
    ```
    vagrant halt
    ```

- Or you may destroy the cluster with:
    ```
    vagrant destroy --force
    ```

### Web Interface

Once done with the installation and launch, you can visit the web interface in your browser in (http://127.0.0.1:9000/ui/) (or the port specified in the config file instead of 9000 if modified).

You will see a Home page with 5 subpages:
- **Containers**: here you can see and manage all the deployed containers
- **Hosts**: here you can see and manage all hosts as well as their containers
- **Apps**: here you can see and manage all apps as well as their associated containers
- **Services**: here you can see and manage all services of ServerlessContainers
- **Rules**: here you can see and manage all rules that are followed by the services

## Used tools
- [Vagrant](https://www.vagrantup.com/) - IaC tool for deploying the virtual cluster
- [VirtualBox](https://www.virtualbox.org) - VM Software to support the machines of the cluster
- [Ansible](https://www.ansible.com/) - Configuration Management Tool
- [LXD](https://linuxcontainers.org/lxd/) - LXC Containers management tool
- [Django](https://www.djangoproject.com/) - Web development framework
- [Python](https://www.python.org) - Programming language

## Authors

* **&Oacute;scar Castellanos Rodr&iacute;guez**
* **Roberto R. Exp&oacute;sito** (https://gac.udc.es/~rober/)
* **Jonatan Enes &Aacute;lvarez** (https://gac.udc.es/~jonatan/)

## License
This project is distributed as free software and is publicly available under the GNU GPLv3 license (see the [LICENSE](LICENSE) file for more details).
