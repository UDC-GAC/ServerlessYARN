#!/usr/bin/python

import yaml
import os
import requests
import json
import subprocess
import sys

scriptDir = os.path.realpath(os.path.dirname(__file__))
sys.path.append(scriptDir + "/../services/serverless_containers_web/ui")
from utils import DEFAULT_APP_VALUES, DEFAULT_LIMIT_VALUES, DEFAULT_RESOURCE_VALUES, request_to_state_db

APPS_DIR = "apps"
APP_CONFIG_FILENAME = "app_config.yml"
## Keys
# Apps
MANDATORY_APP_KEYS = []
OPTIONAL_APP_KEYS_WITH_DEFAULT = ["start_script", "stop_script"]
OPTIONAL_APP_KEYS = ["files_dir", "install_script", "app_jar"]
OTHER_APP_KEYS = ["name", "names", "app_type", "framework"] # Other keys that are handled differently. This list is for documentation purposes only, it is not meant to be used in the script
SUPPORTED_APP_TYPES = ["base", "generic_app", "hadoop_app", "spark_app"]
SUPPORTED_EXTRA_FRAMEWORKS = ["spark"]
# Resources
MANDATORY_RESOURCE_KEYS = ["max", "min"]
OPTIONAL_RESOURCE_KEYS_WITH_DEFAULT = ["weight"]
OPTIONAL_RESOURCE_KEYS = []
# Limits
MANDATORY_LIMIT_KEYS = []
OPTIONAL_LIMIT_KEYS_WITH_DEFAULT = ["boundary", "boundary_type"]
OPTIONAL_LIMIT_KEYS = []

if __name__ == "__main__":

    general_config_file = scriptDir + "/../config/config.yml"
    with open(general_config_file, "r") as f:
        general_config = yaml.load(f, Loader=yaml.FullLoader)

    url = "http://{0}:{1}/structure/apps".format(general_config['server_ip'],general_config['orchestrator_port'])

    if "apps" not in general_config or not general_config["apps"]:
        print("No application was specified in config.yml")
        exit(0)

    apps_to_load = general_config["apps"].split(",")

    resources = ["cpu", "mem", "disk_read", "disk_write", "energy"]

    for app_dir in apps_to_load:

        # Open app configuration file
        app_config_file_path = "{0}/../{1}/{2}/{3}".format(scriptDir, APPS_DIR, app_dir, APP_CONFIG_FILENAME)
        try:
            with open(app_config_file_path, "r") as f:
                config = yaml.load(f, Loader=yaml.FullLoader)
        except FileNotFoundError:
            print("App configuration file doesn't exist: {0}. Check that '{1}' exists in apps directory "
                  "and has an app_config.yml inside".format(app_config_file_path, app_dir))
            break

        #app_dir = os.path.relpath(os.path.split(app_config_file_path)[0], "{0}/../apps".format(scriptDir))
        #app_dir = os.path.split(app_config_file_path)[0]

        app_config = {}
        app_config["app"] = {}
        app_config["limits"] = {}
        app_config["app"]["guard"] = False
        app_config["app"]["subtype"] = "application"

        ## App name (or names, if multiple apps are selected)
        # Name or names of applications (we allow "name" or "names" as key)
        if "name" in config and config["name"] != "": alias_name_key = "name"
        elif "names" in config and config["names"] != "": alias_name_key = "names"
        else: raise Exception("Missing mandatory parameter {0} or {1}".format("name", "names"))
        app_names = config[alias_name_key].split(",")

        ## App keys
        for key in MANDATORY_APP_KEYS + OPTIONAL_APP_KEYS_WITH_DEFAULT + OPTIONAL_APP_KEYS:
            if key in config: app_config["app"][key] = "{0}/{1}".format(app_dir, config[key])
            elif key in MANDATORY_APP_KEYS: raise Exception("Missing mandatory parameter {0}".format(key))
            elif key in OPTIONAL_APP_KEYS_WITH_DEFAULT: app_config["app"][key] = DEFAULT_APP_VALUES[key]
            elif key in OPTIONAL_APP_KEYS: app_config["app"][key] = ""

        # App type and extra frameworks
        if "app_type" in config and config["app_type"] != "":
            app_type = config["app_type"]
            if app_type not in SUPPORTED_APP_TYPES: raise Exception("{0} is not a supported app type. Currently supported app types: {1}".format(app_type, SUPPORTED_APP_TYPES))
        elif "install_script" in app_config["app"] and app_config["app"]["install_script"] != "": app_type = "generic_app"
        else: app_type = "base"

        if "framework" in config and config["framework"] != "":
            app_config["app"]["framework"] = config["framework"]
            if app_config["app"]["framework"] not in SUPPORTED_EXTRA_FRAMEWORKS: raise Exception("{0} is not a supported extra framework. Currently supported extra frameworks: {1}".format(app_config["app"]["framework"], SUPPORTED_EXTRA_FRAMEWORKS))
            if app_config["app"]["framework"] == "spark": app_type = "spark_app" # we update app_type based on extra framework to build the corresponding container image
        elif app_type == "hadoop_app": app_config["app"]["framework"] = "hadoop"
        else: app_config["app"]["framework"] = ""

        ## Resources and limits
        app_config["app"]["resources"] = {}
        app_config["limits"]["resources"] = {}
        for resource in resources:

            if resource == "disk" and (not general_config['disk_capabilities'] or not general_config['disk_scaling']): continue
            if resource == "energy" and not general_config['power_budgeting']: continue

            app_config["app"]["resources"][resource] = {}
            app_config["app"]["resources"][resource]['guard'] = False

            # Resource keys
            for key in MANDATORY_RESOURCE_KEYS + OPTIONAL_RESOURCE_KEYS_WITH_DEFAULT + OPTIONAL_RESOURCE_KEYS:
                if "{0}_{1}".format(resource,key) in config: app_config["app"]["resources"][resource][key] = config["{0}_{1}".format(resource,key)]
                elif key in MANDATORY_RESOURCE_KEYS: raise Exception("Missing mandatory parameter {0}".format(key))
                elif key in OPTIONAL_RESOURCE_KEYS_WITH_DEFAULT: app_config["app"]["resources"][resource][key] = DEFAULT_RESOURCE_VALUES[key]
                elif key in OPTIONAL_RESOURCE_KEYS: app_config["app"]["resources"][resource][key] = ""

            ## Limit keys
            app_config["limits"]["resources"][resource] = {}
            for key in MANDATORY_LIMIT_KEYS + OPTIONAL_LIMIT_KEYS_WITH_DEFAULT + OPTIONAL_LIMIT_KEYS:
                if "{0}_{1}".format(resource,key) in config: app_config["limits"]["resources"][resource][key] = config["{0}_{1}".format(resource,key)]
                elif key in MANDATORY_LIMIT_KEYS: raise Exception("Missing mandatory parameter {0}".format(key))
                elif key in OPTIONAL_LIMIT_KEYS_WITH_DEFAULT: app_config["limits"]["resources"][resource][key] = DEFAULT_LIMIT_VALUES[key]
                elif key in OPTIONAL_LIMIT_KEYS: app_config["limits"]["resources"][resource][key] = ""

        for app_name in app_names:
            app_config["app"]["name"] = app_name

            full_url = "{0}/{1}".format(url, app_config["app"]["name"])

            error_message = "Error adding app {0}".format(app_config['app']['name'])
            error, _ = request_to_state_db(full_url, "put", error_message, app_config)

            if error:
                if "already exists" in error:
                    print("App {0} already exists".format(app_config['app']['name']))
                    continue

            if (error == ""):

                files_dir = os.path.basename(app_config['app']['files_dir'])
                install_script = os.path.basename(app_config['app']['install_script'])
                app_jar = os.path.basename(app_config['app']['app_jar'])

                argument_list = [app_dir, files_dir, install_script, app_type, app_jar]
                error_message = "Error creating app {0} with directory {1}".format(app_config['app']['name'], app_dir)

                ## Process script
                rc = subprocess.Popen(["{0}/../services/serverless_containers_web/ui/scripts/create_app.sh".format(scriptDir), *argument_list], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = rc.communicate()

                # Log ansible output
                print(out.decode("utf-8"))

                if rc.returncode != 0:
                    error = "{0}: {1}".format(error_message, err.decode("utf-8"))
                    raise Exception(error)
            else:
                raise Exception(error)

            print("Added succesfully: {0}".format(app_config))