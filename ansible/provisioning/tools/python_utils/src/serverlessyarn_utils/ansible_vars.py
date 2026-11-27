#!/usr/bin/env python
"""Load Ansible variable files (e.g., vars/main.yml) from Python, rendering the Jinja2 expressions as Ansible would.

Only what these variable files use is supported: references between variables, standard Jinja2 filters and
the 'env' lookup (e.g., "{{ lookup('env', 'HOME') }}"). Any value that cannot be rendered (e.g., it uses an
Ansible-only filter or lookup, or an undefined variable) is kept as its raw string.
"""
import os
import yaml
import jinja2

MAX_RENDER_PASSES = 10


def _lookup(plugin, *terms, **kwargs):
    """Replacement for Ansible's 'lookup' function supporting only the 'env' plugin (values read from the environment)"""
    if plugin != "env":
        raise ValueError("Unsupported Ansible lookup plugin '{0}'".format(plugin))
    values = [os.environ.get(term, kwargs.get("default", "")) for term in terms]
    return values[0] if len(values) == 1 else ",".join(values)


_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)
_jinja_env.globals["lookup"] = _lookup


def _render(value, context):
    if isinstance(value, dict):
        return {k: _render(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, context) for v in value]
    if isinstance(value, str) and ("{{" in value or "{%" in value):
        try:
            return _jinja_env.from_string(value).render(context)
        except Exception:
            # Keep the raw value: it may depend on variables or plugins only available within Ansible
            return value
    return value


def render_ansible_vars(raw_vars, overrides=None):
    """
    Render the Jinja2 expressions in a dictionary of Ansible variables.

    Args:
        raw_vars (dict): variables as read from the YAML files
        overrides (dict): already rendered variables taking precedence over raw_vars (e.g., the ones in config.yml,
                          which Ansible playbooks load after vars/main.yml), also usable within the expressions
    Returns:
        dict: the variables in raw_vars with their final values
    """
    overrides = overrides or {}
    rendered = {k: overrides.get(k, v) for k, v in raw_vars.items()}

    # Variables may reference other variables that are also templated (e.g., bind_dir -> bind_path -> installation_path),
    # so render repeatedly until nothing changes (each pass resolves one more level of references)
    for _ in range(MAX_RENDER_PASSES):
        context = {**rendered, **overrides}
        new_rendered = {k: v if k in overrides else _render(v, context) for k, v in rendered.items()}
        if new_rendered == rendered:
            break
        rendered = new_rendered

    return rendered


def load_ansible_vars(vars_files, overrides=None):
    """
    Load and render Ansible variable files; later files take precedence over earlier ones (as in 'vars_files').

    Args:
        vars_files (list): paths of the YAML variable files
        overrides (dict): see render_ansible_vars
    Returns:
        dict: the rendered variables
    """
    raw_vars = {}
    for vars_file in vars_files:
        with open(vars_file, "r") as f:
            raw_vars.update(yaml.load(f, Loader=yaml.FullLoader) or {})
    return render_ansible_vars(raw_vars, overrides)
