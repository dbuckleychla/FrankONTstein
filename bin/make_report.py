#!/usr/bin/env python3
import base64
import html
import json
import sys
from pathlib import Path
from urllib.parse import quote


def render(data):
    rows = []
    for row in data['analyses']:
        links = ' '.join(f'<a href="{quote(p, safe="/")}">{html.escape(Path(p).name)}</a>' for p in row.get('files', []))
        rows.append('<tr>' + ''.join('<td>' + html.escape(str(row.get(k, ''))) + '</td>' for k in ['sample', 'analysis', 'status']) + '<td>' + links + '</td></tr>')
    return '<!doctype html><meta charset="utf-8"><title>FrankONTstein results</title><h1>FrankONTstein results</h1><p>Caller results are reported separately. See manifest.json and pipeline_info for provenance and execution status.</p><table><tr><th>Sample</th><th>Analysis</th><th>Status</th><th>Files</th></tr>' + ''.join(rows) + '</table>'

if __name__ == '__main__':
    data = json.loads(base64.b64decode(sys.argv[1]))
    Path('manifest.json').write_text(json.dumps(data, indent=2))
    Path('index.html').write_text(render(data))
