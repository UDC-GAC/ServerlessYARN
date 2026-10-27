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

### How hosts are grouped
For each host, the destination path of the task is rendered with the variables of that host (inventory vars, facts, play/role/task vars, etc.). Hosts are then grouped by the file they target, identified by the shared file system and the path within it, and only one host per group (the first one by name) performs the write. This way:
- If all hosts write the same file (e.g., `/shared/app.conf`), only one of them writes it.
- If each host writes a different file (e.g., `/shared/file-{{ inventory_hostname }}`), all of them write their own file.
- In loops, hosts are compared on the same loop item.

### Limitations
- Only exact matches of the destination path are detected. Overlapping paths (e.g., a host writing a directory recursively while another one writes a file inside it) are treated as different targets.
- If the destination path cannot be rendered for other hosts (e.g., it is set through `module_defaults`), all hosts are assumed to write the same path. A warning with the reason is shown in that case, and the reason is also added to the message of the skipped hosts.
- For `pip`, the install path of other hosts is approximated from the task args and their `ansible_env.HOME` fact, without probing them.

In those specific cases, you can disable the plugin at the task level using `smart_sharedfs_enabled: false`, or simply call the underlying Ansible module directly using its fully-qualified collection name (for example, 'ansible.builtin.copy' instead of just 'copy').