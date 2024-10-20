#!/usr/bin/python

import yaml
import os
import sys
import requests
import json
from bs4 import BeautifulSoup
import subprocess

if __name__ == "__main__":

    scriptDir = os.path.realpath(os.path.dirname(__file__))

    general_config_file = scriptDir + "/../config/config.yml"
    with open(general_config_file, "r") as f:
        general_config = yaml.load(f, Loader=yaml.FullLoader)

    apps_to_load = general_config["apps"].split(",")

    resources = ["cpu", "mem", "disk", "energy"]

    for app_config_file in apps_to_load:

        # Open app configuration file
        app_config_file_path = "{0}/../{1}".format(scriptDir, app_config_file)
        with open(app_config_file_path, "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        app_dir = os.path.relpath(os.path.split(app_config_file_path)[0], "{0}/../apps".format(scriptDir))
        #app_dir = os.path.split(app_config_file_path)[0]

        app_config = {}
        app_config["app"] = {}
        app_config["limits"] = {}
        app_config["app"]["guard"] = False
        app_config["app"]["subtype"] = "application"

        ## Basic properties
        for key in ["name"]:
            if key in config:
                app_config["app"][key] = config[key]
            else:
                if key in []: # Not mandatory parameters
                    app_config["app"][key] = ""
                else:
                    raise Exception("Missing mandatory parameter {0}".format(key))

        ## Files
        for key in ["files_dir", "install_script", "start_script", "stop_script", "app_jar"]:
            if key in config:
                app_config["app"][key] = "{0}/{1}".format(app_dir, config[key])
            else:
                if key in ["install_script", "app_jar"]: # Not mandatory parameters
                    app_config["app"][key] = ""
                else:
                    raise Exception("Missing mandatory parameter {0}".format(key))

        ## Resources
        app_config["app"]["resources"] = {}
        app_config["limits"]["resources"] = {}
        for resource in resources:

            if resource == "disk" and not general_config['disk_scaling']: continue
            if resource == "energy" and not general_config['power_budgeting']: continue

            ## Max and min resources
            app_config["app"]["resources"][resource] = {}
            app_config["app"]["resources"][resource]['guard'] = False
            for key in ["max", "min"]:
                if "{0}_{1}".format(resource,key) in config:
                    app_config["app"]["resources"][resource][key] = config["{0}_{1}".format(resource,key)]
                else:
                    if key in []:
                        app_config["app"]["resources"][resource][key] = ""
                    else:
                        raise Exception("Missing mandatory parameter {0}".format(key))

            ## Limits
            app_config["limits"]["resources"][resource] = {}
            key = "boundary"
            if "{0}_{1}".format(resource,key) in config:
                app_config["limits"]["resources"][resource][key] = config["{0}_{1}".format(resource,key)]
            else:
                if key in []:
                    app_config["limits"]["resources"][resource][key] = ""
                else:
                    raise Exception("Missing mandatory parameter {0}".format(key))

        url = "http://{0}:{1}/structure/apps".format(general_config['server_ip'],general_config['orchestrator_port'])
        full_url = "{0}/{1}".format(url, app_config["app"]['name'])
        headers = {'Content-Type': 'application/json'}

        r = requests.put(full_url, data=json.dumps(app_config), headers=headers)

        error = ""
        if (r != "" and r.status_code != requests.codes.ok):
            soup = BeautifulSoup(r.text, features="html.parser")
            if "already exists" in soup.get_text().strip():
                print("App {0} already exists".format(app_config['app']['name']))
                continue
            else:
                error = "Error adding app {0}: {1}".format(app_config['app']['name'],soup.get_text().strip())

        if (error == ""):

            if app_config["app"]['install_script'] != "":

                app_name = app_config['app']['name']
                #definition_file = "{0}_container.def".format(app_config['app']['name'].replace(" ", "_"))
                definition_file = "hadoop_app.def" if app_config['app']['name'] == "hadoop_app" else "generic_app.def"
                image_file = "{0}.sif".format(app_config['app']['name'].replace(" ", "_"))
                files_dir = app_config['app']['files_dir'] # Not necessary with new app management
                install_script = app_config['app']['install_script'] # Not necessary with new app management

                argument_list = [definition_file, image_file, app_config['app']['name'], files_dir, install_script]
                error_message = "Error creating app {0}".format(app_config['app']['name'])

                ## Process script
                #rc = subprocess.Popen(["{0}/../services/serverless_containers_web/ui/scripts/create_app.sh".format(scriptDir), *argument_list], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                rc = subprocess.Popen(["{0}/../services/serverless_containers_web/ui/scripts/create_app.sh".format(scriptDir), *[app_name]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = rc.communicate()

                # Log ansible output
                print(out.decode("utf-8"))

                if rc.returncode != 0:
                    error = "{0}: {1}".format(error_message, err.decode("utf-8"))
                    raise Exception(error)
        else:
            raise Exception(error)

        print("Added succesfully: {0}".format(app_config))