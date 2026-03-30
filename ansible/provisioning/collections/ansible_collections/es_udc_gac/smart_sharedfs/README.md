## Smart Shared FS collection
This is a collection of action plugins that act as wrappers for common Ansible modules capable of creating, modifying or deleting files or directories.

Those modules often fail when they run in parallel on multiple hosts that access the same path on a shared file system. For example, if two hosts attempt to copy a file to their HOME directory, but both share that directory via NFS, the copy may fail due to simultaneous writes to the same file.

This collection allows checking the type of file system to which the module will attempt to write, and to run that module on a host only if the file system is detected as shared.

### Requirements
- Ansible "mounts" facts gathered

### Modules currently supported
- blockinfile
- copy
- file
- git
- lineinfile
- make
- pip
- synchronize
- template
- unarchive

### Variables
- smart_sharedfs_enabled (boolean): enable or disable this collection
- smart_sharedfs_debug (boolean): enable or disable additional debug messages when running in verbose mode

### Limitations
Currently, this collection of plugins does not distinguish between different destination paths within the same shared file system across different hosts. This means, for example, that if two hosts write different files (such as `file-{{ inventory_hostname }}`), only one of them will actually perform the write operation if both files share the same destination file system.

In those specific cases, you can disable the plugin at the task level using `smart_sharedfs_enabled: false`, or simply call the underlying Ansible module directly using its fully-qualified collection name (for example, 'ansible.builtin.copy' instead of just 'copy').