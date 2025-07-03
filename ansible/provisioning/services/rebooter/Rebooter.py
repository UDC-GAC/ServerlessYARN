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
import os

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

SERVICE_NAME = "rebooter"
BDW_SERVICES = ["EVE_TIMES", "OPENTSDB"]
SC_SERVICES = ["orchestrator", "database_snapshoter", "structure_snapshoter", "guardian", "scaler", "refeeder", "sanity_checker", "rebalancer"]
SY_SERVICES = ["web_interface", "celery", "redis_server"]

SERVICES = BDW_SERVICES + SC_SERVICES + SY_SERVICES

ONLY_VIRTUAL_MODE = ["EVE_TIMES"]

scriptDir = os.path.realpath(os.path.dirname(__file__))
playbook_dir = scriptDir + "/../.."
debug = True

## Update config file
class EventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.src_path.endswith(".yml"):  # Only process files ending in .yml, excluding .template files
            log_info(event, debug)
            ## Run the playbook to update the config file
            rc = RunnerConfig(
                private_data_dir=playbook_dir,
                playbook="load_config_playbook.yml",
                inventory='../ansible.inventory'
            )
            rc.prepare()
            r = Runner(config=rc)
            r.run()
            log_info("Updated config file to due modification on modules", debug)

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

def stop_opentsdb():
    ## Stop OpenTSDB
    rc = RunnerConfig(
        private_data_dir=playbook_dir,
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
    date_file = str(time.strftime("%d-%m-%y", time.localtime()))
    logging.basicConfig(filename="{0}_{1}.log".format(SERVICE_NAME, date_file), level=logging.INFO)
    global debug
    global SERVICES

    ## Test connection for OPENTSDB setup
    config_file = scriptDir + "/../../config/config.yml"
    with open(config_file, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    opentsdb_url = "127.0.0.1"
    opentsdb_port = config['opentsdb_port']
    opentsdb_server = 'http://' + opentsdb_url + ":" + str(opentsdb_port)

    virtual_mode = config['virtual_mode']
    if not virtual_mode:
        SERVICES = [x for x in SERVICES if x not in ONLY_VIRTUAL_MODE]

    ## Playbook running setup
    rc = RunnerConfig(
        private_data_dir=playbook_dir,
        playbook="launch_playbook.yml",
        tags='restart_services',
        inventory='../ansible.inventory'
    )
    rc.prepare()
    r = Runner(config=rc)

    ## Setup watchdog to monitor config file changes
    event_handler = EventHandler()
    observer = PollingObserver()
    observer.schedule(event_handler, scriptDir + "/../../config/modules/", recursive=True)
    observer.start()
    log_info("Monitoring config changes on {0}".format(scriptDir + "/../../config/modules/"), debug)

    try:
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
                log_info("{},{}: {}".format(r.status, r.rc, r.stderr),debug)

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
        observer.stop()
        log_warning(SERVICE_NAME.capitalize() + " stopped by user", debug)
    observer.join()

def main():
    try:
        check_services()
    except Exception as e:
        log_error("{0} {1}".format(str(e), str(traceback.format_exc())), debug=True)


if __name__ == "__main__":
    main()