# plugins/action/_sharedfs_base.py
import posixpath

from ansible.plugins.action import ActionBase
from ansible.module_utils.six import string_types
from ansible.parsing.mod_args import ModuleArgsParser
from ansible.playbook.block import Block
from ansible.template import Templar

from ansible_collections.es_udc_gac.smart_sharedfs.plugins.module_utils.sharedfs_utils import (
    DEFAULT_SHARED_FS_TYPES, longest_mount, is_shared_fstype, share_id_for_mount, path_within_mount
)

# Variables not returned by the variable manager but set by the strategy (play-wide) or the
# task executor (current loop item). They are kept when rendering the task args of other hosts,
# so that all hosts are compared on the same loop item
EXECUTOR_VARNAMES = ("ansible_current_hosts", "ansible_failed_hosts", "ansible_loop_var", "ansible_index_var", "ansible_loop")

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
        return list(self._task_vars.get('ansible_play_batch', self._task_vars.get('play_hosts', [])))

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

    def _shared_target(self, host, dest):
        """
        Identify the file targeted by dest on host as (share_id, path within the share),
        or None if dest is not on a shared filesystem for that host.
        """
        if not dest:
            return None
        shared, sid, m = self._is_shared_path(host, dest)
        if not shared:
            return None
        if not sid:
            # Mounts are unknown but assumed shared: compare by absolute path
            return ("unknown", posixpath.normpath(dest))
        return (sid, path_within_mount(m, dest))

    def _get_raw_task_args(self):
        """
        Task args as written in the playbook, before templating. self._task.args is already
        templated with the vars of the current host, so it cannot be used for other hosts.
        """
        if not hasattr(self, '_raw_task_args'):
            self._raw_task_args = None
            self._raw_task_args_error = None
            ds = self._task.get_ds()
            if isinstance(ds, dict):
                try:
                    parser = ModuleArgsParser(task_ds=ds, collection_list=self._task.collections)
                    _action, self._raw_task_args, _delegate_to = parser.parse(skip_action_validation=True)
                except Exception as e:
                    self._raw_task_args_error = f"could not parse the raw task args ({type(e).__name__}: {e})"
            else:
                self._raw_task_args_error = f"raw task data is not available (got {type(ds).__name__})"
        return self._raw_task_args

    def _note_dest_fallback(self, host, reason):
        """
        Record why the destination path of host could not be determined, so that it is
        assumed to be the same as the one of the current host.
        """
        if not hasattr(self, '_dest_fallbacks'):
            self._dest_fallbacks = {}
        self._dest_fallbacks[host] = reason
        self._display.warning(
            f"[smart_sharedfs] Task '{self._task.get_name()}': cannot determine the destination of host {host}, "
            f"assuming it is the same as {self._task_vars.get('inventory_hostname')}'s: {reason}"
        )

    def _skipped_result(self, msg, leader):
        reason = getattr(self, '_dest_fallbacks', {}).get(leader)
        if reason:
            msg += f" Destination of {leader} was assumed to be the same because {reason}."
        return {"skipped": True, "changed": False, "msg": msg}

    def _get_task_play(self):
        # Same as Task.get_play(), which is not available in older ansible-core versions (e.g., 2.13)
        parent = self._task._parent
        while not isinstance(parent, Block):
            parent = parent._parent
        return parent._play

    def _get_task_vars_for_host(self, host):
        vm = self._task.get_variable_manager()
        host_vars = vm.get_vars(
            play=self._get_task_play(),
            host=vm._inventory.get_host(host),
            task=self._task,
            _hosts=self._task_vars.get('ansible_play_batch'),
            _hosts_all=self._task_vars.get('ansible_play_hosts_all'),
        )
        executor_varnames = list(EXECUTOR_VARNAMES) + [self._task_vars.get(v) for v in ("ansible_loop_var", "ansible_index_var")]
        for v in executor_varnames:
            if v and v in self._task_vars:
                host_vars[v] = self._task_vars[v]
        return host_vars

    def _render_task_args_for_host(self, host, argnames):
        """
        Template the given task args with the vars of another host. Returns None if they
        cannot be rendered, or the subset of args found in the task otherwise.
        """
        raw_args = self._get_raw_task_args()
        if raw_args is None:
            self._note_dest_fallback(host, self._raw_task_args_error)
            return None

        if '_variable_params' in raw_args:
            # Args given as a single template (e.g., 'args: "{{ copy_args }}"'), render it whole
            raw_subset = {'_variable_params': raw_args['_variable_params']}
        else:
            raw_subset = {k: raw_args[k] for k in argnames if k in raw_args}

        if not any(m in str(raw_subset) for m in ("{{", "{%")):
            # Nothing to template, so args are the same for all hosts
            return raw_subset

        try:
            templar = Templar(loader=self._loader, variables=self._get_task_vars_for_host(host))
            rendered = templar.template(raw_subset)
        except Exception as e:
            self._note_dest_fallback(host, f"the task args could not be rendered with its vars ({type(e).__name__}: {e})")
            return None

        if '_variable_params' in rendered:
            rendered = rendered['_variable_params']
            if not isinstance(rendered, dict):
                self._note_dest_fallback(host, "the task args template did not render to a dict")
                return None
        return {k: rendered[k] for k in argnames if k in rendered}

    def _get_dest_path_for_host(self, host, dest):
        """
        Path that host will write to in this task, given that the current host writes to dest.
        Override in subclasses whose path is not directly taken from PATH_ARGNAMES.
        """
        if host == self._task_vars.get('inventory_hostname'):
            return dest
        rendered_args = self._render_task_args_for_host(host, self.PATH_ARGNAMES)
        if rendered_args is None:
            # Args could not be rendered: assume all hosts write to the same path
            return dest
        host_dest = self._get_dest_path(rendered_args)
        if not host_dest:
            self._note_dest_fallback(host, f"none of {', '.join(self.PATH_ARGNAMES)} was found in the raw task args (set via module_defaults?)")
            return dest
        return host_dest

    def _elect_leader(self, hosts, dest):
        """
        Hosts writing the same file in a shared filesystem (same share and same path within it)
        are grouped together, and only one of them (the leader) performs the write.
        Returns (share_id, leader) for the current host, or (None, None) if dest is not shared.
        """
        inventory_hostname = self._task_vars.get('inventory_hostname')
        my_target = self._shared_target(inventory_hostname, dest)

        if not my_target:
            # Not on shared fs for this host -> not subject to leader election
            return None, None

        # The leader is the first host (sorted by name) writing to the same target, so only the
        # hosts before the current one need to be checked
        leader = inventory_hostname
        for h in sorted(hosts):
            if h >= inventory_hostname:
                break
            if self._shared_target(h, self._get_dest_path_for_host(h, dest)) == my_target:
                leader = h
                break
        return my_target[0], leader

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
            self._debug(f"{inventory_hostname}: Leader for {dest} on share {my_share_id}, executing.")
            return self._run_module(module_name=module_name, task_vars=self._task_vars, args=args)

        # Else: skip
        msg = (f"Skipped on {inventory_hostname}: destination {dest} is on shared filesystem "
               f"({my_share_id}). Executed on leader host: {leader}.")
        return self._skipped_result(msg, leader)
