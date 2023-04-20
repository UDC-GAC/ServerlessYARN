#!/usr/bin/env bash
pkill -9 -f stress
exit_code = $?
if [ $exit_code -gt 1 ]; then
    exit $exit_code
else
    exit 0
fi