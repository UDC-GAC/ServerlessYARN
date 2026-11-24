#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
port=$1

# Create/update the tables of Django's built-in apps (admin, auth, contenttypes, sessions) in db.sqlite3.
# It is idempotent: already applied migrations are skipped, so it is safe to run on every start.
# The UI does not rely on the database, so a failure here should not prevent the server from starting.
python3 $scriptDir/manage.py migrate --noinput || echo "WARNING: Django migrations could not be applied, starting the server anyway"

python3 $scriptDir/manage.py runserver 0:$port
