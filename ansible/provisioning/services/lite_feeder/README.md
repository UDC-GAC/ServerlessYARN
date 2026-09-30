# lite_feeder

Lite feeder runs inside each container, replacing the original BDWatchdog atop pipeline:
```text
atop <interval> -a -P CPU,cpu,MEM,SWP,NET,PRC,PRM,PRD
  | MetricsFeeder/src/atop/atop_to_json.py | MetricsFeeder/src/pipelines/send_to_OpenTSDB.py
```

It reads `/proc` directly and sends to OpenTSDB (`/api/put`) the same data points: the same metric names, tags, units, two-decimal rounding, and filters as BDWatchdog MetricsFeeder using atop 2.4.0.

| Group | Metrics                                                              | Tags               | Source                            |
| ----- | -------------------------------------------------------------------- | ------------------ | --------------------------------- |
| PRC   | `proc.cpu.user`, `proc.cpu.kernel` (ticks/s)                         | host, pid, command | `/proc/<pid>/stat` utime/stime    |
| PRM   | `proc.mem.virtual`, `proc.mem.resident` (MB)                         | host, pid, command | `/proc/<pid>/stat` vsize/rss      |
| PRD   | `proc.disk.reads.mb`, `proc.disk.writes.mb` (MB/s)                   | host, pid, command | `/proc/<pid>/io` read/write_bytes |
| CPU   | `sys.cpu.usage` (%)                                                  | host               | `/proc/stat`                      |
| cpu   | `sys.cpu.kernel`, `sys.cpu.user`, `sys.cpu.idle`, `sys.cpu.wait` (%) | host, core         | `/proc/stat`                      |
| MEM   | `sys.mem.free` (MB), `sys.mem.usage` (%)                             | host               | `/proc/meminfo`                   |
| SWP   | `sys.swap.free` (MB)                                                 | host               | `/proc/meminfo`                   |
| NET   | `sys.net.in.mb`, `sys.net.out.mb` (Mbit/s), `sys.net.usage` (%)      | host, device       | `/proc/net/dev`, `/sys/class/net` |

The details of the original pipeline are also replicated, including its quirks:
* processes without threads; names truncated to 15 characters; `host` and `command` tags sanitized in the same way as in `json_to_TSDB_json.py`;
* `custom_filter.py` / `value_filter.py`: `kworker`, `systemd`, `migration`, `rcu`, `ksoftirq`, and
  `bioset` are excluded from PRC; PRM excludes nothing (the filter checks the state column); PRD always sends
  `systemd` and excludes `migration`, `rcu`, `ksoftirq`, `bash`, `bioset`, `sshd`, and `ssh`; thresholds of
  0.05 and 10 MB;
* `sys.cpu.usage` counts `iowait` as busy time; `transport` and `network` devices are always reported as
  0.00; `sys.net.usage` is set to the reported speed (0) if the interface does not provide one.

Differences (which do not affect the data points): samples are aligned to interval boundaries (x.000 s); points are sent without gzip in HTTP requests of at most 8000 bytes (OpenTSDB rejects bodies above 8192 bytes, which its HTTP decoder splits in chunks, unless `tsd.http.request.enable_chunked` is set; the original pipeline stays below that limit thanks to gzip); and a failed request is retried once before its points are discarded (the original stopped after 3 failures).

## Usage

Compile with gcc:
```bash
gcc -O2 -o lite_feeder lite_feeder.c
lite_feeder -i 1                      # Run every second, using the OpenTSDB configured in $BDWATCHDOG_PATH/services_config.yml
lite_feeder -i 1 -s -c 5              # Print 5 samples (one JSON object per line, like atop_to_json.py)
lite_feeder -i 1 -H 10.0.0.1 -P 4242 -g PRC,PRM,CPU # Send to a custom OpenTSDB (10.0.0.1)
```

In ServerlessYARN, it is enabled with `container_metrics_feeder: lite` in the configuration:

* the base image (`templates/apps/ubuntu_container.def`) gets `lite_feeder.c`, compiles it and starts it from
  `%startscript`, per-process disk metrics (PRD) are only sent if `disk_capabilities` or `disk_scaling` are enabled;
* Hadoop/Spark applications keep atop + BDWatchdog MetricsFeeder, as they translate Java process names: with
  `lite`, `hadoop_app.def` copies BDWatchdog and installs them itself (`templates/apps/atop_metrics_feeder.j2`, also
  used by the base image with `atop`).

## Validation
On a node with 573 processes and 1s interval (without OpenTSDB):

| Group                | CPU usage (shares) | Memory (MB) |
|----------------------|--------------------|-------------|
| atop (MetricsFeeder) | 7.6                | 29          |
| lite feeder          | 1.2                | 2.2         |

