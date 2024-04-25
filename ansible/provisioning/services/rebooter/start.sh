#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")

## Unset TMUX variable to allow start tmux sessions inside the Rebooter sessions in older versions of tmux
unset TMUX
python3 ${scriptDir}/Rebooter.py