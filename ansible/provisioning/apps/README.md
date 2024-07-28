# Applications directory

This directory stores applications that will be automatically deployed by ServerlessYARN. The directories for each application can have any name except `hadoop_app`, as this name is reserved for deploying Hadoop containers that use a specific definition file. Application directories must have at least the following files:

- **install.sh**: This file will be run during the container build process and will be responsible for installing all the software dependencies necessary to run the application. This file can be understood as a dynamic definition file.
- - **files_dir**: Directory to store any other configuration file/script, if none exist it is not necessary to add this directory. This file can be understood as a dynamic %files section for the definition file.
- **start.sh**: This file can be executed once the container has been built and instanciated. It will be responsible for starting the application.
- **stop.sh**: This file can be executed once the container has been built and instanciated. It will be responsible for stopping the application.
- **app_config.yml**: This file contains the necessary parameters to subscribe the application in ServerlessContainers. You can see an example at sample_app/config.yml.

To use an application, specify the name of its directory as `app_name` parameter in `../config/config.yml` file.