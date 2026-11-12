"""Expose the deterministic loop and libraries while hiding research data and credentials."""
import os
from pathlib import Path

def sandbox_command(directory,venv):
    """Build the Bubblewrap command for one fresh worker process."""
    workspace=Path(directory)/'provider_workspace';workspace.mkdir()
    venv=Path(venv).resolve()
    if not (venv/'bin/python').is_file():raise ValueError('loop_virtual_environment_required')
    args=['bwrap','--die-with-parent','--new-session','--unshare-user','--unshare-pid',
        '--unshare-ipc','--unshare-uts','--unshare-cgroup','--cap-drop','ALL','--ro-bind','/usr','/usr']
    for name in ['/bin','/lib','/lib64','/sbin']:
        if Path(name).is_symlink():args+=['--symlink',os.readlink(name),name]
        elif Path(name).exists():args+=['--ro-bind',name,name]
    args+=['--dir','/etc']
    for name in ['ssl','resolv.conf','hosts','nsswitch.conf','passwd','group','localtime']:
        if Path('/etc',name).exists():args+=['--ro-bind','/etc/'+name,'/etc/'+name]
    args+=['--dir','/opt','--dir','/opt/search-agent',
        '--ro-bind',str(venv),'/opt/search-agent/venv',
        '--ro-bind',str(Path(__file__).with_name('loop.py')),'/opt/search-agent/loop.py',
        '--bind',str(workspace),'/media','--dir','/home','--dir','/home/search',
        '--dir','/mnt','--dir','/srv','--dir','/run','--dir','/root',
        '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--chdir','/media',
        '--clearenv','--setenv','HOME','/home/search','--setenv','USER','search',
        '--setenv','PATH','/opt/search-agent/venv/bin:/usr/bin:/bin',
        '--setenv','PYTHONDONTWRITEBYTECODE','1','--setenv','PYTHONUNBUFFERED','1',
        '--setenv','PIP_NO_INDEX','1','--setenv','LITELLM_LOCAL_MODEL_COST_MAP','True',
        '--setenv','LITELLM_TELEMETRY','False','--',
        '/opt/search-agent/venv/bin/python','/opt/search-agent/loop.py']
    return args
