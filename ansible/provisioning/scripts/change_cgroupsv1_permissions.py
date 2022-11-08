#!/usr/bin/python

import subprocess
import json
import sys

if __name__ == "__main__":   

    ## Get container PID
    group = sys.argv[1]
    container = sys.argv[2]

    process = subprocess.Popen(["sudo", "singularity", "instance", "list", "-j", container], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()
    parsed = json.loads(stdout)

    container_pid = parsed['instances'][0]['pid']


    ## Change group ownership
    CGROUP_PATH = "/sys/fs/cgroup"

    cpu_accounting_dir = "/".join([CGROUP_PATH, "cpuacct", "system.slice", "apptainer-{0}.scope".format(container_pid)])    
    cpu_cpuset_dir = "/".join([CGROUP_PATH, "cpuset", "system.slice", "apptainer-{0}.scope".format(container_pid)])
    memory_limit_dir = "/".join([CGROUP_PATH, "memory", "system.slice", "apptainer-{0}.scope".format(container_pid)])

    process = subprocess.Popen(["sudo", "chgrp", group, "-R", cpu_accounting_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()
    process = subprocess.Popen(["sudo", "chgrp", group, "-R", cpu_cpuset_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()
    process = subprocess.Popen(["sudo", "chgrp", group, "-R", memory_limit_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()

    ## Change files write permissions
    cpu_accounting_path = "/".join([cpu_accounting_dir, "cpu.cfs_quota_us"])    
    cpu_quota_path = "/".join([cpu_accounting_dir, "cpu.cfs_period_us"])   
    cpu_cpuset_path = "/".join([cpu_cpuset_dir, "cpuset.cpus"])
    memory_limit_path = "/".join([memory_limit_dir, "memory.limit_in_bytes"])

    process = subprocess.Popen(["sudo", "chmod", "g+w", cpu_accounting_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()
    process = subprocess.Popen(["sudo", "chmod", "g+w", cpu_quota_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()
    process = subprocess.Popen(["sudo", "chmod", "g+w", cpu_cpuset_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()
    process = subprocess.Popen(["sudo", "chmod", "g+w", memory_limit_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()