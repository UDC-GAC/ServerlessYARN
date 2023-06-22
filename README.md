# AutoServerlessWeb

This project provides a platform for the execution of Big Data workloads through Hadoop YARN in container-based clusters.

The platform provides a serverless environment that supports Singularity/Apptainer containers, scaling their allocated resources to fit them according to the usage in real time.

It is provided an automatic way of deploying the platform through IaC tools such as Ansible, as well as a web interface to easily manage the platform and execute Big Data workloads. The serverless platform may be deployed on an existing cluster or a virtual Vagrant cluster for testing purposes.


## Getting Started

### Prerequisites (for the Vagrant virtual cluster deployment)
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
The platform need to be installed and deployed on a master node (or "server" node), while the containers will be deployed on the remaining nodes of the cluster.

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

- Go back to the root directory of the repository and you may deploy the virtual cluster with Vagrant (if needed):
    ```
    cd ../../
    vagrant up
    ```

**NOTE**: You must ensure **"id_rsa.pub"** doesn't exist when executing "vagrant up" the first time (or after a "vagrant destroy")

- Inside the server node (you may use "vagrant ssh" to log in if using a virtual cluster) go to the **"ansible/provisioning/scripts"** directory inside the platform root directory (accessible from **"/vagrant"** on the virtual cluster). Then execute the script to install and set up all the necessary requirements for the platform and start its services:
    ```
    python3 load_inventory_from_conf.py
    bash start_all.sh
    ```

**NOTE**: When deploying on an existing cluster through SLURM, you may skip the execution of the **"load_inventory_from_conf.py"** script. The inventory will be automatically generated considering the available nodes.


- Once you are done, you can shutdown the virtual cluster (if applicable) exiting the server node and executing:
    ```
    vagrant halt
    ```

- Or you may destroy the virtual cluster with:
    ```
    vagrant destroy --force
    ```

### Web Interface

Once done with the installation and launch, you can visit the web interface in your browser in (<server-ip>:9000/ui/) (or the port specified in the config file instead of 9000 if modified).

You will see a Home page with 5 subpages:
- **Containers**: here you can see and manage all the deployed containers
- **Hosts**: here you can see and manage all hosts as well as their containers
- **Apps**: here you can see and manage all apps as well as their associated containers
- **Services**: here you can see and manage all services of the platform
- **Rules**: here you can see and manage all scaling rules that are followed by the services

## Used tools
- [Vagrant](https://www.vagrantup.com/) - IaC tool for deploying the virtual cluster
- [VirtualBox](https://www.virtualbox.org) - VM Software to support the machines of the cluster
- [Ansible](https://www.ansible.com/) - Configuration Management Tool
- [Apptainer](https://apptainer.org/) - Singularity/Apptainer Containers management tool
- [Django](https://www.djangoproject.com/) - Web development framework
- [Python](https://www.python.org) - Programming language
- [Serverless Containers](https://bdwatchdog.dec.udc.es/serverless/) - Container resource scaling framework
- [BDWatchdog](https://bdwatchdog.dec.udc.es/monitoring/) - Resource monitoring framework


## Authors

* **&Oacute;scar Castellanos-Rodr&iacute;guez** (https://orcid.org/0000-0001-8630-6665)
* **Roberto R. Exp&oacute;sito** (https://gac.udc.es/~rober/)
* **Jonatan Enes** (https://gac.udc.es/~jonatan/)
* **Guillermo L. Taboada** (https://gac.udc.es/~gltaboada/)
* **Juan Touriño** (https://gac.udc.es/~juan/)

## License
This project is distributed as free software and is publicly available under the GNU GPLv3 license (see the [LICENSE](LICENSE) file for more details).
