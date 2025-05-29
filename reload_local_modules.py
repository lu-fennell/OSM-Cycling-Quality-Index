import importlib
import sys
import os.path

def reload(project_dir: str):
    _reload_self()
    _reload_dir(project_dir)

def _reload_self():
    if __name__ in sys.modules:
        importlib.reload(sys.modules[__name__])

def _reload_dir(project_dir: str):
    ms : list = [m for m in sys.modules.copy().values()
        if m is not None and m.__spec__ is not None and m.__spec__.origin is not None]
    ms = [m for m in ms if m.__spec__.origin.startswith(project_dir)]
    if not ms:
        print('WARNING: no modules found to reload')
    for m in ms:
        importlib.reload(m)
