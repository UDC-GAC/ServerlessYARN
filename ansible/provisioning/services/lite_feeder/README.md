# lite_feeder

Lite feeder runs inside each container, replacing the original BDWatchdog atop pipeline:
```text
atop <interval> -a -P CPU,cpu,MEM,SWP,NET,PRC,PRM,PRD
  | MetricsFeeder/src/atop/atop_to_json.py | MetricsFeeder/src/pipelines/send_to_OpenTSDB.py
```

It reads `/proc` directly and sends to OpenTSDB (`/api/put`) the same data points: the same metric names, tags, units, two-decimal rounding, and filters as BDWatchdog MetricsFeeder using atop 2.4.0. It also sends the CPU wait of each process (PRW).

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
| PRW   | `proc.cpu.wait` (ticks/s)                                            | host, pid, command | `/proc/<pid>/task/<tid>/schedstat` |

The details of the original pipeline are also replicated, including its quirks:
* processes without threads; names truncated to 15 characters; `host` and `command` tags sanitized in the same way as in `json_to_TSDB_json.py`;
* `custom_filter.py` / `value_filter.py`: `kworker`, `systemd`, `migration`, `rcu`, `ksoftirq`, and
  `bioset` are excluded from PRC; PRM excludes nothing (the filter checks the state column); PRD always sends
  `systemd` and excludes `migration`, `rcu`, `ksoftirq`, `bash`, `bioset`, `sshd`, and `ssh`; thresholds of
  0.05 and 10 MB;
* `sys.cpu.usage` counts `iowait` as busy time; `transport` and `network` devices are always reported as
  0.00; `sys.net.usage` is set to the reported speed (0) if the interface does not provide one.

Differences (which do not affect the data points): samples are aligned to interval boundaries (x.000 s); points are sent without gzip in HTTP requests of at most 8000 bytes (OpenTSDB rejects bodies above 8192 bytes, which its HTTP decoder splits in chunks, unless `tsd.http.request.enable_chunked` is set; the original pipeline stays below that limit thanks to gzip); and a failed request is retried once before its points are discarded (the original stopped after 3 failures).

## CPU wait (PRW)

`proc.cpu.wait` is the time the threads of each process were runnable but waiting for a CPU. This is the run-queue delay, the second field of
`/proc/<pid>/task/<tid>/schedstat`, and the same state that PSI (cgroup v2 `cpu.pressure`) counts as CPU pressure.

It is given in the same units as `proc.cpu.user` (clock ticks per second, i.e., % of one CPU). Added up by `host`,
it gives the CPU wait of the container in shares. The CPU pressure is `wait / (user + kernel + wait)`: the share of
the CPU demand of the container that was not served.

* It works regarless of the cgroups version (only needs `/proc`).
* Deltas are computed per thread, so a thread that exits does not subtract its accumulated delay. Threads not seen 
  before count since their start, as new processes do. The last interval of a thread that exits is lost.
* It is sent along with `proc.cpu.user` and `proc.cpu.kernel` (with the same filters, also when it is 0.00, so that
  each CPU usage point has its wait), or alone if the process waited ≥ 0.05 ticks/s.

Validation against the PSI in a machine with cgroup v2 (`stress-ng --cpu` in a PID namespace, 1s samples):

| Case                                    | usage | wait | wait/(usage+wait) | PSI some | PSI full |
|-----------------------------------------|-------|------|-------------------|----------|----------|
| 4 threads, quota 200 %                  | 200   | 201  | 50 %              | 50 %     | 50 %     |
| 4 threads, quota 100 %                  | 100   | 302  | 75 %              | 75 %     | 75 %     |
| 4 threads, 4 CPUs, no quota             | 400   | 0    | 0 %               | 0 %      | 0 %      |
| 6 threads on 4 CPUs, no quota           | 402   | 200  | 33 %              | 48 %     | 0 %      |
| 8 threads, 80 ms bursts every 200 ms, quota 400 % | 230 | 197 | 46 %          | 24 %     | 24 %     |

With a CPU-bound load limited by the quota, wait/(usage+wait) equals PSI. It does not match in two cases:
* With contention (more runnable threads than CPUs), PSI `some` counts the time with at least one thread waiting,
  which depends on how the threads are spread over the CPUs.
* With idle phases, PSI divides by wall time and the ratio divides by the demand.

## Usage

Compile with gcc:
```bash
gcc -O2 -o lite_feeder lite_feeder.c
lite_feeder -i 1                      # Run every second, using the OpenTSDB configured in $BDWATCHDOG_PATH/services_config.yml
lite_feeder -i 1 -s -c 5              # Print 5 samples (one JSON object per line, like atop_to_json.py)
lite_feeder -i 1 -g PRC,PRW           # Only per-process CPU usage and CPU wait
lite_feeder -i 1 -H 10.0.0.1 -P 4242 -g PRC,PRM,CPU # Send to a custom OpenTSDB (10.0.0.1)
```

In ServerlessYARN, it is enabled with `container_metrics_feeder: lite` in the configuration (images must be rebuilt):

* the base image (`templates/apps/ubuntu_container.def`) only gets `lite_feeder.c`, compiles it and starts it from
  `%startscript` (tmux session `LITE_FEEDER`, OpenTSDB address given with `-H`/`-P`); neither atop, its build
  dependencies nor BDWatchdog are copied or installed; per-process disk metrics (PRD) are only sent if
  `disk_capabilities` or `disk_scaling` are enabled; CPU wait (PRW) is always sent;
* Hadoop/Spark applications keep atop + BDWatchdog MetricsFeeder, as they translate Java process names: with
  `lite`, `hadoop_app.def` copies BDWatchdog and installs them itself (`templates/apps/atop_metrics_feeder.j2`, also
  used by the base image with `atop`).

## Overhead compared with atop
On a node with 573 processes and 1s interval (without OpenTSDB):

| Group                | CPU usage (shares) | Memory (MB) |
|----------------------|--------------------|-------------|
| atop (MetricsFeeder) | 7.6                | 29          |
| lite feeder          | 1.2                | 2.2         |

