# plugins/action/pip.py
from ._sharedfs_base import SmartSharedFSBase
import shlex
import os
import base64
import json

def _will_pip_install_to_user(extra_args: str,
                            module_args: dict,
                            probe: dict,
                            env_vars: dict) -> bool:
    """
    Decide if pip will (or should) write under the user's home (~/.local) when no
    explicit target was provided.
    - extra_args: the pip CLI flags string
    - module_args: the ansible.builtin.pip arguments (may contain 'virtualenv')
    - probe: dict returned by the remote python probe (is_venv, global_writable, pep668_externally_managed, user_site, home, ...)
    - env_vars: environment for the task (may contain PIP_USER)
    """

    # 0) Explicit destinations = not user site
    for opt in ("--target", "--prefix", "--root"):
        if _extract_option_value(extra_args, opt) is not None:
            return False

    if module_args.get("virtualenv"):
        return False  # venv is explicit, not user site

    # 1) Explicit --user or env forcing user installs
    if _extract_option_value(extra_args, "--user") is not None:
        return True

    if str(env_vars.get("PIP_USER", "")).strip() in ("1", "true", "True"):
        return True  # env forces user installs

    # 2) pip config may set user=true (we recommend caching this once per host)
    # Expect caller to pass these booleans if you pre-queried with `pip config get`
    if env_vars.get("__pip_cfg_install_user_true__") or env_vars.get("__pip_cfg_global_user_true__"):
        return True

    # 3) If not in venv and global is not writable -> historically pip defaults to user
    #    On PEP 668, pip will refuse global; typical next step is user/venv.
    if not probe.get("is_venv", False):
        if probe.get("pep668_externally_managed", False):
            # Treat as "global write forbidden"; your plugin can either inject --user
            # (safe on most distros) or require a venv, depending on your policy.
            return True
        if not probe.get("global_writable", False):
            return True

    return False

def _normalize_opt(option: str) -> str:
    """Ensure option starts with '--' so callers can pass 'cache-dir' or '--cache-dir'."""
    return option if option.startswith('-') else f'--{option}'

def _extract_option_value(extra_args: str,
                        option: str,
                        *,
                        all_occurrences: bool = False,
                        default=None):
    """
    Extract the value(s) assigned to an option inside a shell-like argument string.

    - Supports both '--opt=value' and '--opt value'.
    - A bare flag '--opt' (no explicit value) yields '' (empty string) in the results.
    - Stops option parsing at a standalone '--'.
    - Returns:
        * the last value (default),
        * a list of all values if all_occurrences=True,
        * or 'default' if the option is not present.

    Examples:
        _extract_option_value("--cache-dir=/var/cache --user", "cache-dir") -> "/var/cache"
        _extract_option_value("--target /x --target=/y", "target") -> "/y"
        _extract_option_value("--no-cache-dir", "no-cache-dir") -> ""
        _extract_option_value("--env=FOO=1 --env BAR=2", "env", all_occurrences=True) -> ["FOO=1","BAR=2"]
    """
    tokens = shlex.split(extra_args or '')
    opt = _normalize_opt(option)
    values = []

    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        # Stop parsing options after '--'
        if tok == '--':
            break

        # --opt=value
        if tok.startswith(opt + '='):
            values.append(tok.split('=', 1)[1])
            i += 1
            continue

        # --opt [value?]
        if tok == opt:
            # If next token exists and is not another option, treat as the value
            if i + 1 < n and not tokens[i + 1].startswith('-'):
                values.append(tokens[i + 1])
                i += 2
            else:
                # Bare flag, record presence with empty string
                values.append('')
                i += 1
            continue

        i += 1

    if not values:
        return default
    return values if all_occurrences else values[-1]

class ActionModule(SmartSharedFSBase):
    PATH_ARGNAMES = ()  # no single dest key

    def _pick_remote_python(self, task_vars):
        """
        Best-effort choice of the remote Python executable to probe with.
        Prefer the configured interpreter if available; fall back to python3/python.
        """
        cand = (
            task_vars.get('ansible_python_interpreter') or
            task_vars.get('ansible_facts', {}).get('python', {}).get('executable') or
            'python3'
        )
        return cand

    def _run_remote_python_probe(self, py_exe, task_vars):
        """
        Execute a tiny Python snippet on the *remote host* and return a dict with:
        - is_venv (bool)
        - global_purelib (str)
        - global_writable (bool)
        - pep668_externally_managed (bool)
        - user_site (str)
        - user_base (str)
        - home (str)

        PEP 668 detection uses the presence of the EXTERNALLY-MANAGED file in stdlib. [3](https://github.com/ansible/ansible/issues/85754)
        """
        probe_code = r'''
import os, sys, sysconfig, site, json
info = {}
info["is_venv"] = (getattr(sys, "base_prefix", sys.prefix) != sys.prefix) or bool(os.environ.get("VIRTUAL_ENV"))
paths = sysconfig.get_paths()
info["global_purelib"] = paths.get("purelib")
info["global_writable"] = os.access(info["global_purelib"], os.W_OK) if info["global_purelib"] else False
stdlib = paths.get("stdlib") or ""
info["pep668_externally_managed"] = os.path.exists(os.path.join(stdlib, "EXTERNALLY-MANAGED"))
info["user_site"] = site.getusersitepackages()
info["user_base"] = site.getuserbase()
info["home"] = os.path.expanduser("~")
print(json.dumps(info))
'''
        b64 = base64.b64encode(probe_code.encode('utf-8')).decode('ascii')
        argv = [
            py_exe, "-c",
            # Using base64 avoids shell quoting pitfalls on remote. 
            "import base64,sys;exec(compile(base64.b64decode(%r).decode(),'probe','exec'))" % b64
        ]
        res = self._execute_module(
            module_name="ansible.builtin.command",
            module_args={"argv": argv},
            task_vars=task_vars
        )
        if res.get('rc', 0) != 0:
            raise Exception(f"Python probe failed: {res}")
        try:
            return json.loads(res.get('stdout') or "{}")
        except Exception as e:
            raise Exception(f"Failed to parse probe JSON: {e}; stdout={res.get('stdout')!r}")

    def _pip_config_get(self, py_exe, key, task_vars, *, scope_flag=None):
        """
        Query `python -m pip config get <key>` and return a normalized string value
        ('true'/'false'/raw text) or None if not set.

        scope_flag can be one of ['--user', '--global', '--site'] to force a given scope
        (optional; usually not necessary).
        """
        argv = [py_exe, "-m", "pip", "config"]
        if scope_flag in ("--user", "--global", "--site"):
            argv.append(scope_flag)
        argv += ["get", key]

        res = self._execute_module(
            module_name="ansible.builtin.command",
            module_args={"argv": argv},
            task_vars=task_vars
        )
        if res.get('rc', 0) != 0:
            return None
        out = (res.get('stdout') or "").strip()
        return out.lower() if out else None

    def _collect_pip_user_default_flags(self, py_exe, task_vars):
        """
        Returns a dict of booleans derived from pip config that influence default user installs.
        - __pip_cfg_install_user_true__
        - __pip_cfg_global_user_true__
        """
        val_install_user = self._pip_config_get(py_exe, "install.user", task_vars)
        val_global_user  = self._pip_config_get(py_exe, "global.user",  task_vars)
        return {
            "__pip_cfg_install_user_true__": (val_install_user == "true"),
            "__pip_cfg_global_user_true__":  (val_global_user  == "true"),
        }

    def _build_env_for_will_user(self, task_vars, pip_flags_extra=None):
        """
        Create the env dict for `_will_pip_install_to_user(...)`.
        - Preserves any task- or play-level `environment:`.
        - Adds our computed flags from pip config.
        """
        base_env = {}

        # Task-level env comes from either explicit args or play vars; normalize:
        # (In action plugins, task vars can hold 'environment' from the task scope.)
        task_level_env = (
            self._task.args.get('_environment') or
            task_vars.get('environment') or
            {}
        )
        if isinstance(task_level_env, dict):
            base_env.update(task_level_env)

        if pip_flags_extra:
            base_env.update(pip_flags_extra)

        return base_env

    def _infer_pip_paths(self, args, task_vars):
        extra = (args.get('extra_args') or '').strip()

        # Pick interpreter and probe the remote host
        py_exe = self._pick_remote_python(task_vars)
        probe  = self._run_remote_python_probe(py_exe, task_vars)

        # Read pip config that may imply default user installs
        pip_cfg_flags = self._collect_pip_user_default_flags(py_exe, task_vars)

        # Merge env (keep user-provided env like PIP_USER if present)
        env_vars = self._build_env_for_will_user(task_vars, pip_cfg_flags)

        # virtualenv path
        venv = args.get('virtualenv')

        # explicit install dirs from extra_args
        target = _extract_option_value(extra, '--target')
        prefix = _extract_option_value(extra, '--prefix')
        root   = _extract_option_value(extra, '--root')
        user   = '--user' in extra.split()

        # user site when --user (assume ~/.local)
        home = (task_vars.get('ansible_env') or {}).get('HOME')
        user_site = os.path.join(home, '.local') if ((user and home) or _will_pip_install_to_user(extra, args, probe, env_vars)) else None

        # cache dir (either from extra_args or default)
        cache_dir = _extract_option_value(extra, '--cache-dir')
        if not cache_dir:
            # Default pip cache path depends on OS; for Linux it’s ~/.cache/pip
            # You can compute ~/.cache/pip from $HOME or force a host-local override later.
            cache_dir = os.path.join(home, '.cache', 'pip') if home else None

        paths = {
            'venv': venv,
            'target': target,
            'prefix': prefix,
            'root': root,
            'user_site': user_site,
            'cache': cache_dir,
        }
        return paths

    def run(self, tmp=None, task_vars=None):
        args = self._task.args.copy()
        extra = (args.get('extra_args') or '').strip()

        if task_vars is not None:
            self._task_vars = task_vars

        if not self._enabled():
            # Just call through
            return self._execute_module(module_name="ansible.builtin.pip", module_args=args, task_vars=task_vars)

        # Compute effective write locations (venv, user_site, target, ...)
        paths = self._infer_pip_paths(args, task_vars)

        # Decide if any install target is on shared FS
        install_targets = [paths['venv'], paths['target'], paths['prefix'], paths['root'], paths['user_site']]
        is_shared_any = any(self._is_shared_path(task_vars['inventory_hostname'], p)[0] for p in install_targets if p)

        # If shared install target -> run-once per share
        if is_shared_any:
            # Elect leader using the first shared install target found
            chosen = next(p for p in install_targets if p)
            my_share_id, leader = self._elect_leader(self._get_play_hosts(), chosen)
            if my_share_id and task_vars['inventory_hostname'] != leader:
                return {"skipped": True, "changed": False,
                        "msg": f"pip install path is on shared FS ({my_share_id}); executed on leader {leader}."}

        # Call the underlying module directly (no special action plugin for pip)
        return self._execute_module(module_name="ansible.builtin.pip", module_args=args, task_vars=task_vars)
