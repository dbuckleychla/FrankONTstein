#!/usr/bin/env python3
"""Read-only validation of top-level pins and selected nested gitlinks."""
import json
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
lock=json.loads((root/'dependencies.json').read_text())
def output(*args): return subprocess.check_output(['git',*map(str,args)],cwd=root,text=True).strip()
for name,spec in lock.items():
    path=root/'vendor'/name
    actual=output('-C',path,'rev-parse','HEAD')
    if actual != spec['commit']: raise SystemExit(f'{name}: unexpected commit {actual}')
    for module in spec.get('modules',[]):
        rel='modules/local/'+module
        expected=output('-C',path,'ls-tree','HEAD','--',rel).split()[2]
        current=output('-C',path/rel,'rev-parse','HEAD')
        if expected != current: raise SystemExit(f'{module}: not at pinned gitlink')
        if output('-C',path/rel,'status','--porcelain'): raise SystemExit(f'{module}: modified checkout')
print('All declared dependency commits and nested gitlinks match')
