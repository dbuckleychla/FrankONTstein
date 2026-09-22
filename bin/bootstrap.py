#!/usr/bin/env python3
"""Initialize only declared gitlinks; never follow upstream branches."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / 'dependencies.json').read_text())

def git(*args):
    subprocess.run(['git', *map(str, args)], cwd=root, check=True)

for name, spec in lock.items():
    path = Path('vendor') / name
    git('submodule', 'update', '--init', '--', path)
    actual = subprocess.check_output(['git', '-C', str(root / path), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != spec['commit']:
        raise SystemExit(f'{name}: gitlink {actual} disagrees with dependencies.json')
    if spec.get('modules'):
        git('-C', path, 'submodule', 'update', '--init', '--',
            *['modules/local/' + module for module in spec['modules']])
