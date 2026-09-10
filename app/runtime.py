from pathlib import Path
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
# Modified for standalone extraction; runtime paths are never tool arguments.
def executable(name,default):
    value=os.environ.get(name,default)
    if not Path(value).is_absolute():raise RuntimeError('Runtime paths must be absolute.')
    return value
NODE=executable('RECORDS_DESK_NODE',r'C:\Program Files\nodejs\node.exe')
PYTHON=sys.executable
GH=executable('RECORDS_DESK_GH',r'C:\Program Files\GitHub CLI\gh.exe')
sys.path.insert(0,str(REPO/'connector'))

def clean_env():
    return {k:v for k,v in os.environ.items() if k.upper() in {
        'SYSTEMROOT','WINDIR','TEMP','TMP','LOCALAPPDATA','APPDATA','USERPROFILE','SYSTEMDRIVE',
        'RECORDS_DESK_NODE','RECORDS_DESK_GH'}}

def run(command,*,payload=None,timeout=30):
    return subprocess.run(command,input=payload,capture_output=True,timeout=timeout,env=clean_env(),
        cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def load_catalog():
    result=run([NODE,str(ROOT/'catalog.mjs')],timeout=25)
    if result.returncode or len(result.stdout)>2_000_000:
        raise RuntimeError('Could not load the project catalog.')
    return json.loads(result.stdout)
