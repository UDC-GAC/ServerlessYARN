# plugins/action/make.py
from ._sharedfs_base import SmartSharedFSBase

class ActionModule(SmartSharedFSBase):
    PATH_ARGNAMES = ("chdir", )

    def run(self, tmp=None, task_vars=None):
        return self.run_wrapped(tmp=tmp, task_vars=task_vars, module_name="community.general.make")
