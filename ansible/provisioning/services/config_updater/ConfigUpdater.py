#!/usr/bin/python

import logging
import time
import traceback
from termcolor import colored
import os

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from serverlessyarn_utils.manage_ansible import run_playbook

SERVICE_NAME = "config_updater"

scriptDir = os.path.realpath(os.path.dirname(__file__))
PROVISION_DIR = os.path.abspath(f"{scriptDir}/../..")
MONITORED_DIR = f"{PROVISION_DIR}/config/modules"

debug = True

## Update config file
class EventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if not event.src_path.startswith("template."):  # Exclude template files
            log_info(event, debug)
            ## Run the playbook to update the config file
            run_playbook(playbook_name="load_config_playbook.yml")
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

## Monitor
def monitor_config():
    date_file = str(time.strftime("%d-%m-%y", time.localtime()))
    logging.basicConfig(filename="{0}_{1}.log".format(SERVICE_NAME, date_file), level=logging.INFO)
    global debug

    ## Setup watchdog to monitor config file changes
    event_handler = EventHandler()
    observer = PollingObserver()
    observer.schedule(event_handler, MONITORED_DIR, recursive=True)
    observer.start()
    log_info("Monitoring config changes on {0}".format(MONITORED_DIR), debug)

    try:
        while True:
            time.sleep(3600)

    except KeyboardInterrupt:
        observer.stop()
        log_warning(SERVICE_NAME.capitalize() + " stopped by user", debug)
    observer.join()

def main():
    try:
        monitor_config()
    except Exception as e:
        log_error("{0} {1}".format(str(e), str(traceback.format_exc())), debug=True)


if __name__ == "__main__":
    main()