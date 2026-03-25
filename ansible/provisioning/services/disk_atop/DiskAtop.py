#!/usr/bin/env python3
"""
Monitor per-container I/O activity for Apptainer containers using cgroup v2 io.stat.

Each Apptainer container is expected to have its cgroup at:
    /sys/fs/cgroup/blkio/system.slice/apptainer-<PID>.scope (in cgroups v1)
    or
    /sys/fs/cgroup/system.slice/apptainer-<PID>.scope (in cgroups v2)

The container name shown in the output is the Apptainer instance name,
resolved via `apptainer instance list --json` (pid field used as the join key).
Cgroups whose PID cannot be matched to a known instance are skipped.

Output format (one line per metric per device per container per interval):
    {"metric": "sys.disk.read.ios",  "timestamp": <ts>, "value": <read IOPS>,   "tags": {"host": <instance_name>, "disk": <device>}}
    {"metric": "sys.disk.read.mb",   "timestamp": <ts>, "value": <read MiB/s>,  "tags": {"host": <instance_name>, "disk": <device>}}
    {"metric": "sys.disk.write.ios", "timestamp": <ts>, "value": <write IOPS>,  "tags": {"host": <instance_name>, "disk": <device>}}
    {"metric": "sys.disk.write.mb",  "timestamp": <ts>, "value": <write MiB/s>, "tags": {"host": <instance_name>, "disk": <device>}}

Usage:
    python3 apptainer_io_monitor.py [--interval SECONDS] [--output {text,json}]
                                    [--apptainer-bin PATH]
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import time
from itertools import islice

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CGROUP_PATTERN  = "apptainer-*.scope"

# Maps major:minor device numbers to human-readable names, e.g. "8:0" -> "sda".
# Populated lazily from /sys/block on first use.
_DEVICE_NAME_CACHE: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Apptainer binary resolution
# ---------------------------------------------------------------------------

#def _find_apptainer_bin(override: str | None) -> str:
def _find_apptainer_bin(override: None) -> str:
    """
    Return the path to the apptainer (or singularity) binary.

    Resolution order:
      1. Explicit --apptainer-bin argument.
      2. 'apptainer' on PATH.
      3. 'singularity' on PATH (for older installations).

    Raises RuntimeError if none is found.
    """
    if override:
        if not os.path.isfile(override):
            raise RuntimeError(f"Specified apptainer binary not found: {override!r}")
        return override

    for candidate in ("apptainer", "singularity"):
        path = shutil.which(candidate)
        if path:
            return path

    raise RuntimeError(
        "Neither 'apptainer' nor 'singularity' found on PATH. "
        "Use --apptainer-bin to specify the binary location."
    )


# ---------------------------------------------------------------------------
# Apptainer instance list → {pid: instance_name}
# ---------------------------------------------------------------------------

def get_pid_to_instance(apptainer_bin: str) -> dict[int, str]:
    """
    Run `apptainer instance list --json` and return a mapping of
    {pid: instance_name}.

    Expected JSON structure:
        {
            "instances": [
                {
                    "instance": "cont0",
                    "pid": 105445,
                    "img": "/home/container.sif",
                    ...
                }
            ]
        }

    Returns an empty dict if the command fails, times out, or returns no
    instances.
    """
    try:
        result = subprocess.run(
            ["sudo", apptainer_bin, "instance", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"[warn] Could not run '{apptainer_bin} instance list --json': {exc}", flush=True)
        return {}

    if result.returncode != 0:
        print(
            f"[warn] '{apptainer_bin} instance list --json' exited with code "
            f"{result.returncode}: {result.stderr.strip()}",
            flush=True,
        )
        return {}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"[warn] Failed to parse 'instance list --json' output: {exc}", flush=True)
        return {}

    pid_to_name: dict[int, str] = {}

    for entry in data.get("instances") or []:
        try:
            pid  = int(entry["pid"])
            name = str(entry["instance"])
        except (KeyError, ValueError, TypeError):
            # Malformed entry – skip silently.
            continue
        pid_to_name[pid] = name

    return pid_to_name


# ---------------------------------------------------------------------------
# Device-name resolution
# ---------------------------------------------------------------------------

def resolve_device_name(major_minor: str) -> str:
    """
    Resolve a 'major:minor' string to a block device name (e.g. '8:0' -> 'sda').
    Falls back to the raw 'major:minor' string if the device cannot be resolved.
    Populates a module-level cache on first call.
    """
    if not _DEVICE_NAME_CACHE:
        for dev_path in glob.glob("/sys/block/*/dev"):
            try:
                with open(dev_path) as fh:
                    mm = fh.read().strip()
                # /sys/block/<name>/dev  ->  <name>
                name = dev_path.split("/")[3]
                _DEVICE_NAME_CACHE[mm] = name
            except OSError:
                pass

    return _DEVICE_NAME_CACHE.get(major_minor, major_minor)


# ---------------------------------------------------------------------------
# cgroup discovery and io.stat parsing
# ---------------------------------------------------------------------------

#def _pid_from_scope(scope_path: str) -> int | None:
def _pid_from_scope(scope_path: str):
    """
    Extract the PID from a cgroup scope directory name.

    Example: '/sys/fs/cgroup/system.slice/apptainer-12345.scope' -> 12345
    Returns None if the name does not match the expected pattern.
    """
    basename = os.path.basename(scope_path)     # 'apptainer-12345.scope'
    name     = basename.removesuffix(".scope")  # 'apptainer-12345'
    prefix   = "apptainer-"
    if not name.startswith(prefix):
        return None
    try:
        return int(name[len(prefix):])
    except ValueError:
        return None


def discover_containers(pid_to_instance: dict[int, str], CGROUPS_BASE: str) -> dict[str, str]:
    """
    Discover active Apptainer cgroup scopes and map them to instance names.

    Returns a dict: { scope_path -> instance_name }
    Scopes whose PID is not present in pid_to_instance are silently skipped.
    """
    pattern = os.path.join(CGROUPS_BASE, CGROUP_PATTERN)
    result: dict[str, str] = {}

    for scope_path in sorted(glob.glob(pattern)):
        pid = _pid_from_scope(scope_path)
        if pid is None:
            continue
        instance_name = pid_to_instance.get(pid)
        if instance_name is None:
            # Cgroup exists but apptainer instance list doesn't know about it
            # (e.g. instance already stopped, or started by a different user).
            continue
        result[scope_path] = instance_name

    return result


def read_v1_io_stats(scope_path: str) -> dict[str, dict[str, int]]:
    """
    Parse the blkio.throttle.io_service_bytes_recursive and blkio.throttle.io_serviced_recursive files for a given cgroup scope directory.

    Each device in the files has the following stats:
        MAJ:MIN Read N
        MAJ:MIN Write N
        MAJ:MIN Sync N
        MAJ:MIN Async N
        MAJ:MIN Discard N
        MAJ:MIN Total N

    Returns a dict keyed by 'MAJ:MIN' with sub-dicts containing at least:
        rbytes, wbytes, rios, wios
    Returns an empty dict if io.stat is missing or unreadable (container gone).
    """
    bytes_stat_path = os.path.join(scope_path, "blkio.throttle.io_service_bytes_recursive")
    iops_stat_path = os.path.join(scope_path, "blkio.throttle.io_serviced_recursive")
    result: dict[str, dict[str, int]] = {}

    try:
        # Bytes
        with open(bytes_stat_path) as fh:
            grouped_stats = zip(*[fh] * 6)

            for device_stats in grouped_stats:
                print(device_stats)

                major_minor = device_stats[0].strip().split()[0]
                result[major_minor] = {}

                result[major_minor]['rbytes'] = device_stats[0].strip().split()[2] # Read
                result[major_minor]['wbytes'] = device_stats[1].strip().split()[2] # Write

        # IOPS
        with open(iops_stat_path) as fh:
            grouped_stats = zip(*[fh] * 6)

            for device_stats in grouped_stats:
                print(device_stats)

                major_minor = device_stats[0].strip().split()[0]
                #result[major_minor] = {} ## dict should had been already created in previous loop

                result[major_minor]['rios'] = device_stats[0].strip().split()[2] # Read
                result[major_minor]['wios'] = device_stats[1].strip().split()[2] # Write

    except OSError:
        # Scope vanished between discovery and read – silently skip.
        pass

    return result


def read_v2_io_stats(scope_path: str) -> dict[str, dict[str, int]]:
    """
    Parse the io.stat file for a given cgroup scope directory.

    Each line in io.stat has the form:
        MAJ:MIN rbytes=N wbytes=N rios=N wios=N dbytes=N dios=N ...

    Returns a dict keyed by 'MAJ:MIN' with sub-dicts containing at least:
        rbytes, wbytes, rios, wios
    Returns an empty dict if io.stat is missing or unreadable (container gone).
    """
    io_stat_path = os.path.join(scope_path, "io.stat")
    result: dict[str, dict[str, int]] = {}

    try:
        with open(io_stat_path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                parts       = line.split()
                major_minor = parts[0]      # 'MAJ:MIN'
                stats: dict[str, int] = {}
                for token in parts[1:]:
                    if "=" in token:
                        key, _, raw_val = token.partition("=")
                        try:
                            stats[key] = int(raw_val)
                        except ValueError:
                            pass
                result[major_minor] = stats
    except OSError:
        # Scope vanished between discovery and read – silently skip.
        pass

    return result


# ---------------------------------------------------------------------------
# Snapshot / delta logic
# ---------------------------------------------------------------------------

# { scope_path -> { major_minor -> { stat_key -> cumulative_value } } }
Snapshot = dict[str, dict[str, dict[str, int]]]


def take_snapshot(pid_to_instance: dict[int, str], cgroups_version: int, CGROUPS_BASE: str) -> tuple[Snapshot, dict[str, str]]:
    """
    Capture io stats for every currently-active, named Apptainer cgroup.

    Returns:
        snapshot       - raw cumulative counters keyed by scope_path
        scope_to_name  - mapping of scope_path -> instance_name (for this snapshot)
    """
    scope_to_name = discover_containers(pid_to_instance, CGROUPS_BASE)
    snapshot: Snapshot = {}
    for scope_path in scope_to_name:
        if cgroups_version == "v1":
            io_stats = read_v1_io_stats(scope_path)
        else:
            io_stats = read_v2_io_stats(scope_path)
        if io_stats:
            snapshot[scope_path] = io_stats
    return snapshot, scope_to_name


def compute_deltas(
    prev: Snapshot,
    curr: Snapshot,
    scope_to_name: dict[str, str],
    elapsed: float,
) -> list[dict]:
    """
    Compute per-device, per-container I/O rates from two consecutive snapshots.

    Returns a list of metric dicts ready for JSON serialisation.
    """
    timestamp = int(time.time())
    records: list[dict] = []

    for scope_path, curr_devices in curr.items():
        # Skip containers that weren't in the previous snapshot (just started).
        if scope_path not in prev:
            continue

        prev_devices  = prev[scope_path]
        instance_name = scope_to_name.get(scope_path, os.path.basename(scope_path))

        for major_minor, curr_stats in curr_devices.items():
            if major_minor not in prev_devices:
                continue        # device appeared mid-interval

            prev_stats = prev_devices[major_minor]
            disk       = resolve_device_name(major_minor)

            # Cumulative counter deltas (counters are monotonically increasing).
            d_rios   = curr_stats.get("rios",   0) - prev_stats.get("rios",   0)
            d_wios   = curr_stats.get("wios",   0) - prev_stats.get("wios",   0)
            d_rbytes = curr_stats.get("rbytes", 0) - prev_stats.get("rbytes", 0)
            d_wbytes = curr_stats.get("wbytes", 0) - prev_stats.get("wbytes", 0)

            # Guard against counter resets (e.g. cgroup recreated).
            d_rios   = max(d_rios,   0)
            d_wios   = max(d_wios,   0)
            d_rbytes = max(d_rbytes, 0)
            d_wbytes = max(d_wbytes, 0)

            read_iops  = round(d_rios   / elapsed, 3)
            write_iops = round(d_wios   / elapsed, 3)
            read_mibs  = round(d_rbytes / elapsed / (1024 ** 2), 6)
            write_mibs = round(d_wbytes / elapsed / (1024 ** 2), 6)

            tags = {"host": instance_name, "disk": disk}

            records += [
                {"metric": "sys.disk.read.ios",  "timestamp": timestamp, "value": read_iops,  "tags": tags},
                {"metric": "sys.disk.read.mb",   "timestamp": timestamp, "value": read_mibs,  "tags": tags},
                {"metric": "sys.disk.write.ios", "timestamp": timestamp, "value": write_iops, "tags": tags},
                {"metric": "sys.disk.write.mb",  "timestamp": timestamp, "value": write_mibs, "tags": tags},
            ]

    return records


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def emit(records: list[dict], output_format: str) -> None:
    """Print records to stdout in the requested format."""
    if not records:
        return

    if output_format == "json":
        # Single JSON array per interval (convenient for log ingestion).
        print(json.dumps(records, separators=(",", ":")))
    else:
        # One JSON object per line (default; easy to grep/stream).
        for rec in records:
            print(json.dumps(rec, separators=(", ", ": ")))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poll cgroups I/O stats for Apptainer containers."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Polling interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--cgroups_version",
        type=str,
        default="v1",
        help="Version of cgroups (v1 or v2) (default: v1)",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help=(
            "'text': one JSON object per line (default); "
            "'json': one JSON array per interval"
        ),
    )
    parser.add_argument(
        "--apptainer-bin",
        default=None,
        metavar="PATH",
        help=(
            "Path to the apptainer (or singularity) binary. "
            "Auto-detected from PATH if not specified."
        ),
    )
    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval must be a positive number")

    if args.cgroups_version == "v1":
        CGROUPS_BASE = "/sys/fs/cgroup/blkio/system.slice"
    elif args.cgroups_version == "v2":
        CGROUPS_BASE = "/sys/fs/cgroup/system.slice"
    else:
        parser.error("--cgroups_version must be v1 or v2")

    apptainer_bin = _find_apptainer_bin(args.apptainer_bin)

    # Take the initial snapshot; refresh the instance list at the same time.
    pid_to_instance  = get_pid_to_instance(apptainer_bin)
    prev_snapshot, _ = take_snapshot(pid_to_instance, args.cgroups_version, CGROUPS_BASE)
    prev_time        = time.monotonic()

    while True:
        time.sleep(args.interval)

        curr_time = time.monotonic()
        elapsed   = curr_time - prev_time   # actual elapsed, not requested interval

        # Refresh instance list every cycle so containers that start or stop
        # mid-run are handled automatically.
        pid_to_instance              = get_pid_to_instance(apptainer_bin)
        curr_snapshot, scope_to_name = take_snapshot(pid_to_instance, args.cgroups_version, CGROUPS_BASE)

        records = compute_deltas(prev_snapshot, curr_snapshot, scope_to_name, elapsed)
        emit(records, args.output)

        prev_snapshot = curr_snapshot
        prev_time     = curr_time


if __name__ == "__main__":
    main()