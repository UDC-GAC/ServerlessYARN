
DEFAULT_APP_VALUES = {
    "install_script": "install.sh",
    "start_script": "start.sh",
    "stop_script": "stop.sh",
    "install_files": "install_files",
    "runtime_files": "runtime_files",
    "output_dir": "output_dir",
}

DEFAULT_LIMIT_VALUES = {
    "boundary": 10,
    "boundary_type": "percentage_of_max"
}

DEFAULT_RESOURCE_VALUES = {
    "weight": 1
}

DEFAULT_HDFS_VALUES = {
    "local_output": "/user/{username}",
    "global_output": "/user/{username}"
}

DEFAULT_SERVICE_PARAMETERS = {
    "lv_extension": {
        "threshold": 0.2,
        "polling_frequency": 5,
        "timeout_events": 1
    }
}

SUPPORTED_RESOURCES = {"cpu", "mem", "disk_read", "disk_write", "net", "energy"}

SUPPORTED_FRAMEWORKS = {"hadoop", "spark"}

EXCLUDED_VALUES_LABELS = {"cpu_cores", "alloc_ratio", "rebalanced"}
