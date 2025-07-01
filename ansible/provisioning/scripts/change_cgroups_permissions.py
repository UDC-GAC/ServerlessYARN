#!/usr/bin/python

import subprocess
import json
import sys

if __name__ == "__main__":

    ## Get container PID
    cgroups_version = sys.argv[1]
    singularity_command_alias = sys.argv[2]
    group = sys.argv[3]
    container = sys.argv[4]

    if cgroups_version not in ["v1", "v2"]: raise Exception("Cgroups version {0} not supported, select one of {1}".format(cgroups_version, ["v1", "v2"]))
 
    process = subprocess.Popen(["sudo", singularity_command_alias, "instance", "list", "-j", container], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()
    parsed = json.loads(stdout)

    container_pid = parsed['instances'][0]['pid']


    CGROUP_PATH = "/sys/fs/cgroup"

    if cgroups_version == "v2":
        ## Change group ownership
        cgroup_dir = "/".join([CGROUP_PATH, "system.slice", "apptainer-{0}.scope".format(container_pid)])
        process = subprocess.Popen(["sudo", "chgrp", group, "-R", cgroup_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate()

    if cgroups_version == "v1":
        cgroup_dict = {
            "cpuacct": ["cpu.cfs_quota_us", "cpu.cfs_period_us"],
            "cpuset":  ["cpuset.cpus"],
            "memory":  ["memory.limit_in_bytes"],
            "blkio":   ["blkio.throttle.read_bps_device", "blkio.throttle.write_bps_device"]
        }
    elif cgroups_version == "v2":
        cgroup_dict = {
            "cpu":     ["cpu.max"],
            "cpuset":  ["cpuset.cpus"],
            "memory":  ["memory.max"],
            "io":      ["io.max"]
        }

    for resource in cgroup_dict:
        if cgroups_version == "v1":
            ## Change group ownership
            cgroup_dir = "/".join([CGROUP_PATH, resource, "system.slice", "apptainer-{0}.scope".format(container_pid)])
            process = subprocess.Popen(["sudo", "chgrp", group, "-R", cgroup_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate()

        ## Change files write permissions
        for cgroup_file in cgroup_dict[resource]:
            cgroup_file_path = "/".join([cgroup_dir, cgroup_file])

            process = subprocess.Popen(["sudo", "chmod", "g+w", cgroup_file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate()
