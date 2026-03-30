# plugins/action/_sharedfs_base.py
from ansible.plugins.action import ActionBase
from ansible.module_utils.six import string_types

from ansible_collections.es_udc_gac.smart_sharedfs.plugins.module_utils.sharedfs_utils import (
    DEFAULT_SHARED_FS_TYPES, longest_mount, is_shared_fstype, share_id_for_mount
)

class SmartSharedFSBase(ActionBase):
    # Override in subclasses to extract the path
    PATH_ARGNAMES = ("dest", "path")

    def _get_dest_path(self, task_args):
        for k in self.PATH_ARGNAMES:
            if k in task_args and isinstance(task_args[k], string_types) and task_args[k]:
                return task_args[k]
        return None

    def _get_fact_mounts(self, host):
        hv = self._task_vars.get('hostvars', {})
        facts = hv.get(host, {})
        # ansible_mounts is present when facts are gathered
        return facts.get('ansible_mounts') or facts.get('ansible_facts', {}).get('mounts')

    def _get_play_hosts(self):
        # all hosts for this task execution scope
        return list(self._task_vars.get('play_hosts', []))

    def _shared_types(self):
        return set(self._task_vars.get('smart_sharedfs_fstypes', [])) or DEFAULT_SHARED_FS_TYPES

    def _enabled(self):
        return bool(self._task_vars.get('smart_sharedfs_enabled', True))

    def _assume_shared_when_unknown(self):
        return bool(self._task_vars.get('smart_sharedfs_assume_shared_when_unknown', False))

    def _leader_strategy(self):
        return self._task_vars.get('smart_sharedfs_leader_strategy', 'min_hostname')

    def _debug(self, msg):
        if self._task_vars.get('smart_sharedfs_debug', False):
            self._display.v(f"[smart_sharedfs] {msg}")

    def _is_shared_path(self, host, dest):
        mounts = self._get_fact_mounts(host)
        if not mounts:
            return (self._assume_shared_when_unknown(), None, None)
        m = longest_mount(mounts, dest)
        if not m:
            return (False, None, None)
        fstype = m.get('fstype', '')
        shared = is_shared_fstype(fstype, self._shared_types())
        sid = share_id_for_mount(m) if shared else None
        return (shared, sid, m)

    def _elect_leader(self, hosts, dest):
        """
        Build a map: share_id -> sorted_hosts.
        Decide if current host is leader for its share, and if not shared, return None.
        """
        inventory_hostname = self._task_vars.get('inventory_hostname')
        shared_map = {}
        my_share_id = None

        for h in hosts:
            shared, sid, _m = self._is_shared_path(h, dest)
            if shared and sid:
                shared_map.setdefault(sid, []).append(h)
            if h == inventory_hostname and shared:
                my_share_id = sid

        if not my_share_id:
            # Not on shared fs for this host -> not subject to leader election
            return None, None

        # Determine leader for my share
        candidates = sorted(shared_map.get(my_share_id, []))
        leader = candidates[0] if candidates else None
        return my_share_id, leader

    def _run_module(self, module_name, task_vars, args):
        ## Try getting the action plugin associated with the module if available
        action_plugin = self._shared_loader_obj.action_loader.get(
            module_name,
            task=self._task,
            connection=self._connection,
            play_context=self._play_context,
            loader=self._loader,
            templar=self._templar,
            shared_loader_obj=self._shared_loader_obj,
        )

        if action_plugin:
            return action_plugin.run(task_vars=task_vars)
        else:
            ## Just run the module directly
            return self._execute_module(module_name=module_name, task_vars=task_vars, module_args=args)


    def run_wrapped(self, tmp=None, task_vars=None, module_name=None):
        if task_vars is not None:
            self._task_vars = task_vars

        args = self._task.args.copy()
        dest = self._get_dest_path(args)
        inventory_hostname = task_vars.get('inventory_hostname')

        if not self._enabled() or not dest:
            # Just call through
            return self._run_module(module_name=module_name, task_vars=self._task_vars, args=args)

        play_hosts = self._get_play_hosts()
        my_share_id, leader = self._elect_leader(play_hosts, dest)

        # If not shared for this host -> call through
        if not my_share_id:
            self._debug(f"{inventory_hostname}: {dest} not on shared fs, proceeding.")
            return self._run_module(module_name=module_name, task_vars=self._task_vars, args=args)

        if leader == inventory_hostname:
            self._debug(f"{inventory_hostname}: Leader for share {my_share_id}, executing.")
            return self._run_module(module_name=module_name, task_vars=self._task_vars, args=args)

        # Else: skip
        msg = (f"Skipped on {inventory_hostname}: destination is on shared filesystem "
               f"({my_share_id}). Executed on leader host: {leader}.")
        return {"skipped": True, "changed": False, "msg": msg}