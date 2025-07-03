# ServerlessYARN

This project provides a platform for the execution of Big Data workloads through Hadoop YARN in container-based clusters.

The platform provides a serverless environment that supports Singularity/Apptainer containers, scaling their allocated resources to fit them according to the usage in real time.

It is provided an automatic way of deploying the platform through IaC tools such as Ansible, as well as a web interface to easily manage the platform and execute Big Data workloads. The serverless platform may be deployed on an existing physical cluster, or on a virtual cluster for testing purposes.

### More information
> &Oacute;scar Castellanos-Rodr&iacute;guez, Roberto R. Exp&oacute;sito, Jonatan Enes, Guillermo L. Taboada, Juan Touriño, [Serverless-like platform for container-based YARN clusters](https://doi.org/10.1016/j.future.2024.02.013). Future Generation Computer Systems, 155:256-271, February 2024.

## Getting Started

### Prerequisites

#### For the virtual cluster deployment

- Vagrant
- VirtualBox
- Vagrant plugins: vagrant-hostmanager, vagrant-reload, vagrant-vbguest

> vagrant-reload plugin is only necessary when deploying nodes with cgroups V1, since V2 is the default installation

You may install the vagrant plugins with the following commands:
```
vagrant plugin install vagrant-hostmanager
vagrant plugin install vagrant-reload
vagrant plugin install vagrant-vbguest
```

#### For the physical cluster deployment

- Python
- Ansible
- Passwordless SSH login between nodes

> Only one cluster node (i.e. master node) needs to have Ansible installed and a passwordless SSH login to the remaining ones

### Quickstart
The Serverless platform need to be installed and deployed on the master node (or "server" node), while the containers will be deployed on the remaining cluster nodes (workers or "hosts").

- You can clone this repository and the required frameworks with
    ```
    git clone --recurse-submodules https://github.com/UDC-GAC/ServerlessYARN.git
    ```

- Once cloned, change directory to the root directory
    ```
    cd ServerlessYARN
    ```

- Create configuration modules in YAML format in **ansible/provisioning/config/modules** to customize your environment (templates are provided in the same directory).
    > If these configuration module files are not created, they will be created automatically during startup by copying the corresponding templates.

- You may deploy the virtual cluster with Vagrant (if needed):
    ```
    vagrant up
    ```

- Inside the server node (you can use "vagrant ssh" to log in when using a virtual cluster) go to the **"ansible/provisioning/scripts"** directory within the platform root directory (accessible from **"/vagrant"** on the virtual cluster). Then, execute the script to install and set up all the necessary requirements for the platform and start its services:
    ```
    bash start_all.sh
    ```

    > By default this script will generate an Ansible inventory considering the current configuration. You can skip this phase with the `-s` option to configure the inventory yourself.

    > When deploying on a physical cluster that relies on SLURM for job scheduling, the Ansible inventory will be automatically generated considering the available nodes. Again, you can skip this phase with the `-s` option.


- Once you are done, you can shutdown the virtual cluster (if applicable) exiting the server node and executing:
    ```
    vagrant halt
    ```

- Or you may destroy the whole virtual cluster with:
    ```
    vagrant destroy --force
    ```

- For deployments on physical clusters relying on SLURM you may consider the sample script for sbatch provided in the **"slurm"** directory.

### Web Interface

Once done with the installation and launch, you can visit the web interface in your browser in *{server-ip}*:9000/ui (or the port specified in the config file instead of 9000 if modified).

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

* **&Oacute;scar Castellanos-Rodr&iacute;guez** (https://gac.udc.es/~oscar.castellanos/)
* **Roberto R. Exp&oacute;sito** (https://gac.udc.es/~rober/)
* **Jonatan Enes** (https://gac.udc.es/~jonatan/)
* **Guillermo L. Taboada** (https://gac.udc.es/~gltaboada/)
* **Juan Touriño** (https://gac.udc.es/~juan/)

## License
This project is distributed as free software and is publicly available under the GNU GPLv3 license (see the [LICENSE](LICENSE) file for more details).
