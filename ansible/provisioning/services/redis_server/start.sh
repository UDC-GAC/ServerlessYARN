#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
installation_dir=$1

cd $installation_dir/redis/src
./redis-server