#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
autoreload=${1:-false}

PROVISION_DIR=$(realpath $scriptDir/../..)
WEB_DIR=$PROVISION_DIR/services/serverless_containers_web

## Seconds given to running tasks to finish before the worker is forcibly restarted (only used with autoreload)
AUTORELOAD_KILL_AFTER=60

cd $WEB_DIR

CELERY_CMD=(celery -A serverless_containers_web worker -Ofair -P gevent -l INFO -f $scriptDir/celery_`date +%d-%m-%y`.log)

if [ "${autoreload,,}" == "true" ]; then
    ## Development only: restart the worker whenever the Python code it runs changes
    # SIGTERM triggers a Celery warm shutdown (running tasks are allowed to finish) and SIGKILL is sent after the timeout
    # Celery is not restarted when it exits on its own (e.g., a syntax error) to avoid a crash loop, it waits for the next change instead
    # Polling is forced because inotify does not receive changes made from the host on shared folders (e.g., vboxsf in virtual mode)
    # Only the code run by the worker is watched (non-recursively): the ui/background package with the tasks and their helpers,
    # the Celery/Django setup, the serverlessyarn_utils package and the only state_database script imported by the tasks
    WATCHED_PATTERNS=(
        '**/ui/background/*.py'
        '**/serverless_containers_web/celery.py'
        '**/serverless_containers_web/settings.py'
        '**/serverlessyarn_utils/*.py'
        '**/state_database/limit_containers_bw.py'
    )
    exec watchmedo auto-restart \
        -d $WEB_DIR/ui/background \
        -d $WEB_DIR/serverless_containers_web \
        -d $PROVISION_DIR/tools/python_utils/src/serverlessyarn_utils \
        -d $PROVISION_DIR/scripts/state_database \
        -p "$(IFS=';'; echo "${WATCHED_PATTERNS[*]}")" \
        --debug-force-polling \
        --signal SIGTERM \
        --kill-after $AUTORELOAD_KILL_AFTER \
        --debounce-interval 1 \
        --no-restart-on-command-exit \
        -- "${CELERY_CMD[@]}"
else
    exec "${CELERY_CMD[@]}"
fi
