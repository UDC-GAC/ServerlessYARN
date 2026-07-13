#!/usr/bin/python

import logging
import time
import traceback
import libtmux
from termcolor import colored
import yaml
import requests
import json
import os

from serverlessyarn_utils.manage_ansible import run_playbook

SERVICE_NAME = "rebooter"
BDW_SERVICES = ["EVE_TIMES", "OPENTSDB"]
SC_SERVICES = ["orchestrator", "database_snapshoter", "structure_snapshoter", "guardian", "scaler", "refeeder", "sanity_checker", "rebalancer", "config_updater"]
SY_SERVICES = ["web_interface", "celery", "redis_server"]
ONLY_VIRTUAL_MODE = ["EVE_TIMES"]

SERVICES = BDW_SERVICES + SC_SERVICES + SY_SERVICES

scriptDir = os.path.realpath(os.path.dirname(__file__))
debug = True

## Logging
def log_info(message, debug):
    logging.info("[{0}] INFO: {1}".format(get_time_now_string(), message))
    if debug:
        print("[{0}] INFO: {1}".format(get_time_now_string(), message))

def log_warning(message, debug):
    logging.warning("[{0}] INFO: {1}".format(get_time_now_string(), message))
    if debug:
        print(colored("[{0}] WARN: {1}".format(get_time_now_string(), message), "yellow"))

def log_error(message, debug):
    logging.error("[{0}] INFO: {1}".format(get_time_now_string(), message))
    if debug:
        print(colored("[{0}] ERROR: {1}".format(get_time_now_string(), message), "red"))

def get_time_now_string():
    return str(time.strftime("%H:%M:%S", time.localtime()))

## Reboot methods
def stop_opentsdb():
    ## Stop OpenTSDB
    run_playbook(playbook_name="stop_services_playbook.yml", tags="stop_opentsdb")
    log_info("OpenTSDB service stopped", debug)

def test_opentsdb_connection(opentsdb_server):
    session = requests.Session()
    start = int(time.time())
    end = int(time.time())
    query = dict(start=start, end=end, queries=list())

    try:
        r = session.post("{0}/{1}".format(opentsdb_server, "api/query"), data=json.dumps(query), 
            headers={'content-type': 'application/json', 'Accept': 'application/json'},timeout=10)

        if r.status_code == 200 or r.status_code == 400:
            log_info("OpenTSDB service working properly", debug)
        else:
            log_warning("OpenTSDB service reports some problems, going to stop", debug)
            stop_opentsdb()

    except requests.ConnectionError:
        log_warning("OpenTSDB service down", debug)
    except requests.exceptions.ReadTimeout:
        log_warning("OpenTSDB service reports some problems, going to stop", debug)
        stop_opentsdb()

def check_services():
    date_file = str(time.strftime("%d-%m-%y", time.localtime()))
    logging.basicConfig(filename="{0}_{1}.log".format(SERVICE_NAME, date_file), level=logging.INFO)
    global debug
    global SERVICES

    config_file = scriptDir + "/../../config/config.yml"
    with open(config_file, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    virtual_mode = config['virtual_mode']
    if not virtual_mode:
        SERVICES = [x for x in SERVICES if x not in ONLY_VIRTUAL_MODE]

    deploy_local_opentsdb = config['deploy_local_opentsdb']
    if not deploy_local_opentsdb:
        SERVICES.remove('OPENTSDB')
    else:
        opentsdb_url = "127.0.0.1"
        opentsdb_port = config['opentsdb_port']
        opentsdb_server = 'http://' + opentsdb_url + ":" + str(opentsdb_port)

    # Wait a few seconds to avoid conflicts when retrieving tmux sessions
    time.sleep(10)

    try:
        while True:

            server = libtmux.Server()
            sessions_missing = 0

            try:
                ## OpenTSBD test
                if 'OPENTSDB' in SERVICES:
                    test_opentsdb_connection(opentsdb_server)

                for service in SERVICES:
                    service_session = server.find_where({ "session_name": service })
                    if not service_session:
                        sessions_missing += 1
                        log_warning("{0} session missing".format(service), debug)

            except libtmux.exc.LibTmuxException:
                sessions_missing += 1
                log_warning("No service started", debug)

            if sessions_missing:
                ## restart services
                run_playbook(playbook_name="launch_playbook.yml", tags="restart_services")

            else:
                log_info("All services started", debug)

            log_info("Services checked", debug)
            log_info("-------------------------------------", debug)

            delay = 300
            time_waited = 0
            heartbeat_delay = 60  # seconds

            while time_waited < delay:
                time.sleep(heartbeat_delay)
                time_waited += heartbeat_delay

    except KeyboardInterrupt:
        log_warning(SERVICE_NAME.capitalize() + " stopped by user", debug)

def main():
    try:
        check_services()
    except Exception as e:
        log_error("{0} {1}".format(str(e), str(traceback.format_exc())), debug=True)


if __name__ == "__main__":
    main()