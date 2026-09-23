#!/usr/bin/env python3
import argparse
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
    qc_rows = []
    for q in data.get('qc', []):
        a = q.get('alignment', {})
        values = [q['sample'], (a.get('counts') or {}).get('primary_reads'), a.get('alignment_rate'), a.get('on_enrichment_fraction_mapped'), q.get('methylation', {}).get('genome', {}).get('combined', {}).get('sites')]
        qc_rows.append('<tr>' + ''.join('<td>' + html.escape(str(v)) + '</td>' for v in values) + '<td><a href="' + quote(q['sample'], safe='') + '/qc/index.html">QC report</a></td></tr>')
    qc_table = '<h2>Sample QC</h2><table><tr><th>Sample</th><th>Primary reads</th><th>Alignment rate</th><th>On-enrichment fraction</th><th>CpGs detected</th><th>Report</th></tr>' + ''.join(qc_rows) + '</table>' if qc_rows else ''
    return '<!doctype html><meta charset="utf-8"><title>FrankONTstein results</title><h1>FrankONTstein results</h1><p>Caller results are reported separately. See manifest.json and pipeline_info for provenance and execution status.</p><table><tr><th>Sample</th><th>Analysis</th><th>Status</th><th>Files</th></tr>' + ''.join(rows) + '</table>' + qc_table

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('payload'); p.add_argument('--qc-dir')
    args = p.parse_args()
    data = json.loads(base64.b64decode(args.payload))
    if args.qc_dir:
        data['qc'] = []
        for path in sorted(Path(args.qc_dir).glob('*/metrics.json')):
            q = json.loads(path.read_text())
            a = q.get('alignment', {})
            data['qc'].append({'sample': q['sample'], 'alignment': {k:a.get(k) for k in ['counts','alignment_rate','on_enrichment_fraction_mapped']},
                'methylation': {'genome': {'combined': {'sites': q.get('methylation', {}).get('genome', {}).get('combined', {}).get('sites')}}}})
    Path('manifest.json').write_text(json.dumps(data, indent=2))
    Path('index.html').write_text(render(data))
