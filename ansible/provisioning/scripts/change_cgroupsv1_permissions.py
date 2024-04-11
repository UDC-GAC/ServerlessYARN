#!/usr/bin/python

import subprocess
import json
import sys

if __name__ == "__main__":

    ## Get container PID
    singularity_command_alias = sys.argv[1]
    group = sys.argv[2]
    container = sys.argv[3]

    process = subprocess.Popen(["sudo", singularity_command_alias, "instance", "list", "-j", container], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()
    parsed = json.loads(stdout)

    container_pid = parsed['instances'][0]['pid']


    CGROUP_PATH = "/sys/fs/cgroup"

    cgroup_dict = {}
    cgroup_dict["cpuacct"] = ["cpu.cfs_quota_us", "cpu.cfs_period_us"]
    cgroup_dict["cpuset"]  = ["cpuset.cpus"]
    cgroup_dict["memory"]  = ["memory.limit_in_bytes"]
    cgroup_dict["blkio"]   = ["blkio.throttle.read_bps_device", "blkio.throttle.write_bps_device"]

    for resource in cgroup_dict:
        cgroup_dir = "/".join([CGROUP_PATH, resource, "system.slice", "apptainer-{0}.scope".format(container_pid)])

        ## Change group ownership
        process = subprocess.Popen(["sudo", "chgrp", group, "-R", cgroup_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate()

        ## Change files write permissions
        for cgroup_file in cgroup_dict[resource]:
            cgroup_file_path = "/".join([cgroup_dir, cgroup_file])

            process = subprocess.Popen(["sudo", "chmod", "g+w", cgroup_file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate()
