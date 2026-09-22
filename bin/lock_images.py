#!/usr/bin/env python3
"""Resolve public OCI references to immutable manifests, without running images."""
import argparse
import json
import re
import subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--sources', default='assets/image_sources.json')
p.add_argument('--preprocess', required=True, help='Published custom preprocessing image')
p.add_argument('--nasvar', required=True, help='Published NASVAR image retaining its license')
p.add_argument('--output', default='images.lock.json')
a = p.parse_args()
images = json.loads(Path(a.sources).read_text())
images.update(preprocess=a.preprocess, nasvar=a.nasvar)
locked = {}
for name, image in images.items():
    text = subprocess.check_output(['docker','buildx','imagetools','inspect',image], text=True)
    match = re.search(r'^Digest:\s+(sha256:[a-f0-9]{64})\s*$', text, re.M)
    if not match: raise SystemExit(f'{name}: no immutable manifest digest returned')
    # Keep repository, discard tag without confusing registry port numbers.
    repository = image.split('@')[0]
    if ':' in repository.rsplit('/',1)[-1]: repository = repository.rsplit(':',1)[0]
    locked[name] = repository + '@' + match.group(1)
Path(a.output).write_text(json.dumps(locked, indent=2) + '\n')
