#!/usr/bin/env python
from ansible_runner import Runner, RunnerConfig
import os
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

scriptDir = os.path.realpath(os.path.dirname(__file__))
PROVISION_DIR = f"{scriptDir}/../../.."
INVENTORY_FILE = "../ansible.inventory.yml" ## relative to PROVISION_DIR

# Ansible runner doc: https://ansible.readthedocs.io/projects/runner/en/stable/ansible_runner/

# Configure and run playbooks
def run_adhoc(hosts, module, module_args=None, extravars=None, ignore_failure=False):
    """
    Args:
        hosts (list): list of hosts on which the playbook will be run
        module (str): name of ansible module to run, e.g., shell
        module_args (str): string containing the arguments for specified module, e.g., the command to run with the shell module
        extravars (dict): dictionary of extra variables
        ignore_failure (bool): do not raise an exception if an error is triggered runing the task
    """

    ## Ad-hoc command setup
    rc = RunnerConfig(
        private_data_dir=PROVISION_DIR, ## required parameter even though it is not executing a playbook
        artifact_dir="/tmp/ansible_artifacts",
        host_pattern=",".join(hosts),
        module=module,
        module_args=module_args,
        extravars=extravars if extravars else None,
        inventory=INVENTORY_FILE
    )
    rc.prepare()
    r = Runner(config=rc)
    status = r.run()

    if status[1] != 0 and not ignore_failure:
        raise Exception("Ad-hoc command has failed on hosts {0}, with module {1} and module_args {2}. Please consult Celery log under services/celery for further details".format(hosts, module, module_args))

def run_playbook(playbook_name, tags=None, limit=None, extravars=None, ignore_failure=False):
    """
    Args:
        playbook_name (str): playbook to run
        tags (list): list of tags
        limit (list): list of hosts on which the playbook will be run
        extravars (dict): dictionary of extra variables
        ignore_failure (bool): do not raise an exception if an error is triggered runing the playbook
    """

    ## Playbook running setup
    rc = RunnerConfig(
        private_data_dir=PROVISION_DIR,
        artifact_dir="/tmp/ansible_artifacts",
        playbook=playbook_name,
        tags=",".join(tags) if tags else None,
        limit=",".join(limit) if limit else None,
        extravars=extravars if extravars else None,
        inventory=INVENTORY_FILE,
        fact_cache=os.path.expanduser("~/.ansible_fact_cache"),
    )

    rc.prepare()
    r = Runner(config=rc)
    status = r.run()

    if status[1] != 0 and not ignore_failure:
        printable_extravars = json.dumps(extravars, sort_keys=False, indent=4) if extravars is not None else None

        # Format detailed error output
        detailed_error = format_ansible_output(r)

        # Log the formatted output
        logger.error(f"\n{'#'*80}\nPlaybook Execution Failed\n{'#'*80}")
        logger.error(f"Playbook: {playbook_name}")
        logger.error(f"Hosts: {limit}")
        logger.error(f"Tags: {tags}")
        logger.error(f"Extra vars:\n{printable_extravars}")
        logger.error(f"\nDetailed Error Output:\n{detailed_error}")
        logger.error(f"{'#'*80}\n")

        raise Exception("Playbook {0} has failed on hosts {1}, with tags {2}. Please consult Celery log under services/celery for further details".format(playbook_name, limit, tags))

    # Create a dict to store ouptut variables
    ouptut = {}
    task_timings = {}

    # Process events to extract registered variables
    for event in r.events:
        if event.get('event') == 'runner_on_ok':
            # Get the event data which contains registered variables
            event_data = event.get('event_data', {})
            task_name = event_data.get('task')
            if 'res' in event_data and 'ansible_facts' in event_data['res']:
                # Store ansible facts
                ouptut.update(event_data['res']['ansible_facts'])
            if 'res' in event_data and 'stdout' in event_data['res']:
                # Store command outputs
                ouptut[f"{task_name}_stdout"] = event_data['res']['stdout']

            # Extract task duration
            if 'start' in event_data and 'end' in event_data:
                start = datetime.fromisoformat(event_data['start'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(event_data['end'].replace('Z', '+00:00'))
                duration = (end - start).total_seconds()
                task_timings[task_name] = duration

    return ouptut, task_timings

def format_ansible_output(runner):
    """Format ansible runner output for better readability"""
    output_lines = []

    for event in runner.events:
        event_data = event.get('event_data', {})
        event_type = event.get('event')

        # Capture task failures
        if event_type in ['runner_on_failed', 'runner_on_async_failed']:
            task = event_data.get('task', 'Unknown task')
            host = event_data.get('host', 'Unknown host')
            output_lines.append(f"\n{'='*60}")
            output_lines.append(f"FAILED TASK: {task}")
            output_lines.append(f"HOST: {host}")
            output_lines.append(f"{'='*60}")

            res = event_data.get('res', {})
            if 'msg' in res:
                output_lines.append(f"Message: {res['msg']}")
            if 'stderr' in res:
                output_lines.append(f"STDERR:\n{res['stderr']}")
            if 'stdout' in res:
                output_lines.append(f"STDOUT:\n{res['stdout']}")
            if 'exception' in res:
                output_lines.append(f"Exception:\n{res['exception']}")

        # Capture unreachable hosts
        elif event_type == 'runner_on_unreachable':
            host = event_data.get('host', 'Unknown host')
            output_lines.append(f"\n{'='*60}")
            output_lines.append(f"UNREACHABLE HOST: {host}")
            output_lines.append(f"{'='*60}")
            res = event_data.get('res', {})
            if 'msg' in res:
                output_lines.append(f"Message: {res['msg']}")

    return "\n".join(output_lines) if output_lines else "No detailed error information available"