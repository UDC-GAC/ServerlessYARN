#!/bin/bash
#SBATCH -t 72:00:00
#SBATCH --nodes 2
#SBATCH --exclusive

echo SLURM_JOB_NODELIST=$SLURM_JOB_NODELIST
echo SLURM_JOB_CPUS_PER_NODE=$SLURM_JOB_CPUS_PER_NODE
echo SLURM_JOB_NUM_NODES=$SLURM_JOB_NUM_NODES
echo SLURM_MEM_PER_NODE=$SLURM_MEM_PER_NODE

## Load modules
module load gnu8/8.3.0
module load python/3.8.13
module load jdk/openjdk/8u382

sleep 259200
