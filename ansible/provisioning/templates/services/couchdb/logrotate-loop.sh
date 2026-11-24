#!/usr/bin/env bash

LOGROTATE_CONFIG="/etc/logrotate.d/couchdb"
ROTATE_PERIOD=18000 # 5 hours

while true; do

  # Sleep until next rotation
  sleep ${ROTATE_PERIOD}

  # Rotate CouchDB logs
  echo "[$(date -u)] Rotating logs using logrotate config at ${LOGROTATE_CONFIG}"
  /usr/sbin/logrotate -s /var/log/couchdb/logrotate.status ${LOGROTATE_CONFIG}

done

