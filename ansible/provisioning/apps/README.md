# Applications directory

This directory stores applications that can be deployed by ServerlessYARN. The directories for each application can have any name except `hadoop_app`, as this name is reserved for deploying Hadoop containers that use a specific definition file. Application directories can have the following files:

- **[Mandatory] start script**: This file will be executed once the container has been built and instanciated. It will be responsible for starting the application.
- **[Mandatory] stop script**: This file can be executed once the container has been built and instanciated. It will be responsible for stopping the application.
- **[Optional] install script**: This file can be executed during the container build process to install additional software dependencies needed by the application.
- **[Optional] files directory**: Directory to store any additional file or directory needed during the installation, startup or shutdown of the application.

Apps can then be created on the web interface or by running the python script `../scripts/load_apps_from_config.py`. This script requires first creating a file named **app_config.yml** in the corresponding application directories with the necessary parameters to subscribe the application(s) in ServerlessContainers and set the `apps` parameter in the `../config/config.yml` with the respective application directories.

You can see a full example of all these files at the `sample_app` directory.