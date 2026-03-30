# plugins/module_utils/sharedfs_utils.py
from pathlib import PurePosixPath

DEFAULT_SHARED_FS_TYPES = {
    "nfs", "nfs4", "cifs", "smbfs", "glusterfs", "ceph", "cephfs",
    "gfs2", "lustre", "gpfs", "ocfs2", "afs", "sshfs",
}

def normalize_path(p):
    # PurePosixPath avoids controller OS differences; dest should be absolute on *nix
    return str(PurePosixPath(p))

def longest_mount(mounts, dest):
    dest = normalize_path(dest)
    # mounts is list of dicts with 'mount', 'device', 'fstype'
    # choose the longest mount path that is a prefix of dest (slash-boundary)
    best = None
    best_len = -1
    for m in mounts or []:
        mp = m.get("mount")
        if not mp:
            continue
        if dest == mp or dest.startswith(mp.rstrip("/") + "/"):
            if len(mp) > best_len:
                best = m
                best_len = len(mp)
    return best

def is_shared_fstype(fstype, shared_types=None):
    if shared_types is None:
        shared_types = DEFAULT_SHARED_FS_TYPES
    return fstype in shared_types

def share_id_for_mount(mount):
    # mount['device'] is the most stable unique identity for NFS/CIFS/Gluster/…
    # e.g., "server:/export/path" (NFS), "//server/share" (CIFS)
    fstype = mount.get("fstype", "unknown")
    device = mount.get("device", "unknown")
    # Some FS report dynamic device (e.g., ceph), we still include fstype prefix.
    return f"{fstype}:{device}"