# plugins/action/template.py
from ._sharedfs_base import SmartSharedFSBase

class ActionModule(SmartSharedFSBase):
    def run(self, tmp=None, task_vars=None):
        return self.run_wrapped(tmp=tmp, task_vars=task_vars, module_name="ansible.builtin.template")
