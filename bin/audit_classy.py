#!/usr/bin/env python3
"""Record missing Classy sidecars without discarding embedded model results."""
import argparse
import json
from pathlib import Path


def audit(path):
    path=Path(path); data=json.loads(path.read_text());missing=set()
    def walk(value):
        if isinstance(value,dict):
            for v in value.values():walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
        elif isinstance(value,str) and value.startswith('classy/'):
            relative=Path(value).relative_to('classy')
            if '..' not in relative.parts and not (path.parent/relative).is_file():missing.add(str(relative))
    walk(data)
    result=dict(status='warning' if missing else 'complete', missing_sidecars=sorted(missing),
                missing_count=len(missing), message='Embedded results remain available; missing sidecars require rendering/publication review.' if missing else 'All referenced sidecars exist.')
    (path.parent/'artifact_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    (path.parent/'artifact_audit.txt').write_text(result['message']+'\n'+'\n'.join(sorted(missing))+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('json');audit(p.parse_args().json)
