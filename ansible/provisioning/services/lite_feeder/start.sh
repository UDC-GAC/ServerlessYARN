#!/usr/bin/env bash

# Per-process disk metrics (PRD) only if disks are used by the platform
METRICS="CPU,cpu,MEM,SWP,NET,PRC,PRM{{ ',PRD' if (disk_capabilities | bool) or (disk_scaling | bool) else '' }}"

lite_feeder -i {{ sampling_frequency }} -g "${METRICS}" -H {{ opentsdb_url }} -P {{ opentsdb_port }}