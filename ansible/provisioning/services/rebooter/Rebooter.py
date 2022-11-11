#!/usr/bin/python

import logging
import time
import traceback
import libtmux
import subprocess
from termcolor import colored
from ansible_runner import Runner, RunnerConfig
import yaml
import requests
import json

SERVICE_NAME = "rebooter"
BDW_SERVICES = ["EVE_TIMES", "OPENTSDB"]
SC_SERVICES = ["orchestrator", "database_snapshoter", "structure_snapshoter", "guardian", "scaler", "refeeder", "sanity_checker", "rebalancer"]
ASW_SERVICES = ["web_interface", "celery"]

SERVICES = BDW_SERVICES + SC_SERVICES + ASW_SERVICES

private_data_dir = "../.."
debug = True

## Logging
def log_info(message, debug):
    logging.info(message)
    if debug:
        print("[{0}] INFO: {1}".format(get_time_now_string(), message))

def log_warning(message, debug):
    logging.warning(message)
    if debug:
        print(colored("[{0}] WARN: {1}".format(get_time_now_string(), message), "yellow"))

def log_error(message, debug):
    logging.error(message)
    if debug:
        print(colored("[{0}] ERROR: {1}".format(get_time_now_string(), message), "red"))

def get_time_now_string():
    return str(time.strftime("%H:%M:%S", time.localtime()))

def stop_opentsdb():
    ## Stop OpenTSDB
    rc = RunnerConfig(
        private_data_dir=private_data_dir,
        playbook="stop_services_playbook.yml",
        tags='stop_opentsdb',
        inventory='../ansible.inventory'
    )
    rc.prepare()
    r = Runner(config=rc)
    r.run()
    log_info("OpenTSDB service stopped",debug)

def test_opentsdb_connection(opentsdb_server):
    session = requests.Session()
    start = int(time.time())
    end = int(time.time())
    query = dict(start=start, end=end, queries=list())

    try:
        r = session.post("{0}/{1}".format(opentsdb_server, "api/query"), data=json.dumps(query), 
            headers={'content-type': 'application/json', 'Accept': 'application/json'},timeout=10)

        if r.status_code == 200 or r.status_code == 400:
            log_info("OpenTSDB service working properly",debug)
        else:
            log_warning("OpenTSDB service reports some problems, going to stop",debug)
            stop_opentsdb()

    except requests.ConnectionError:
        log_warning("OpenTSDB service down",debug)
    except requests.exceptions.ReadTimeout:
        log_warning("OpenTSDB service reports some problems, going to stop",debug)
        stop_opentsdb()

def check_services():
    logging.basicConfig(filename=SERVICE_NAME + '.log', level=logging.INFO)
    global debug

    ## Test connection for OPENTSDB setup
    config_file = private_data_dir + "/config/config.yml"
    with open(config_file, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    opentsdb_url = "127.0.0.1"
    opentsdb_port = config['opentsdb_port']
    opentsdb_server = 'http://' + opentsdb_url + ":" + str(opentsdb_port)

    ## Playbook running setup
    rc = RunnerConfig(
        private_data_dir=private_data_dir,
        playbook="launch_playbook.yml",
        tags='restart_services',
        inventory='../ansible.inventory'
    )

    rc.prepare()
    r = Runner(config=rc)

    while True:

        server = libtmux.Server()
        sessions_missing = 0

        try:

            ## OpenTSBD test
            test_opentsdb_connection(opentsdb_server)

            for service in SERVICES:
                service_session = server.find_where({ "session_name": service })
                if not service_session:
                    sessions_missing += 1
                    log_warning("{0} session missing".format(service),debug)

        except libtmux.exc.LibTmuxException:
            sessions_missing += 1
            log_warning("No service started",debug)

        if sessions_missing:
            ## restart services
            r.run()
            log_info("{}: {}".format(r.status, r.rc),debug)

        else:
            log_info("All services started", debug)


        log_info("Services checked", debug)

        delay = 300
        time_waited = 0
        heartbeat_delay = 60  # seconds

        while time_waited < delay:
            time.sleep(heartbeat_delay)
            time_waited += heartbeat_delay

def main():
    try:
        check_services()
    except Exception as e:
        log_error("{0} {1}".format(str(e), str(traceback.format_exc())), debug=True)


if __name__ == "__main__":
    main()