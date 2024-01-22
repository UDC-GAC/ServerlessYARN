#!/bin/bash 
#
#SBATCH -o <directory to save output>/%x_%j.out
#SBATCH -t <max time to keep the platform deployed, e.g., 03:00:00>
#SBATCH -p <cluster partition>
#SBATCH --nodes <number of nodes including master node>
#SBATCH --exclusive
#SBATCH -C <constraints, e.g., SSD>
#SBATCH --exclude=<nodes to be excluded, if any>
#SBATCH --nodelist=<specific nodes to be included, if any>
#SBATCH --signal=B:USR1@60

set -e

PLATFORM_HOME=$HOME/ServerlessYARN

echo SLURM_JOB_NODELIST=$SLURM_JOB_NODELIST
echo SLURM_JOB_CPUS_PER_NODE=$SLURM_JOB_CPUS_PER_NODE
echo SLURM_JOB_NUM_NODES=$SLURM_JOB_NUM_NODES
echo SLURM_MEM_PER_NODE=$SLURM_MEM_PER_NODE

## Load modules
module load gnu8/8.3.0
module load python/3.8.13
module load jdk/openjdk/8u382

cleanup()
{
    echo "Cleanup called at $(date)"
    cd $PLATFORM_HOME/ansible/provisioning
    bash scripts/stop_all.sh
}

echo ""
sleep 10

trap 'cleanup' SIGCONT SIGTERM USR1

cd $PLATFORM_HOME/ansible/provisioning
bash scripts/start_all.sh

# Hold job until timeout or a scancel is sent
TIME_LIMIT=`squeue -j $SLURM_JOB_ID --Format=timelimit -h`
SLEEP_TIME=`date -d "1970-01-01 ${TIME_LIMIT} Z" +%s`
sleep ${SLEEP_TIME} &
wait
