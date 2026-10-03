#!/usr/bin/env python3
import argparse
import base64
import html
import json
import sys
from pathlib import Path
from report_presentation import CSS, number
from urllib.parse import quote


def render(data):
    rows = []
    for row in data['analyses']:
        links = ' '.join(f'<a href="{quote(p, safe="/")}">{html.escape(Path(p).name)}</a>' for p in row.get('files', []))
        if row.get('analysis') == 'methylation':
            links += ' <a href="' + quote(row['sample'], safe='') + '/methylation/classy/' + quote(row['sample'], safe='') + '.artifact_audit.txt">Classy completeness audit</a>'
        rows.append('<tr>' + ''.join('<td>' + html.escape(str(row.get(k, ''))) + '</td>' for k in ['sample', 'analysis', 'status']) + '<td>' + links + '</td></tr>')
    qc_rows = []
    for q in data.get('qc', []):
        a = q.get('alignment', {})
        values = [q['sample'], number((a.get('counts') or {}).get('primary_reads')), number(a.get('alignment_rate'),percent=True), number(a.get('on_enrichment_fraction_mapped'),percent=True), q.get('methylation', {}).get('genome', {}).get('combined', {}).get('sites')]
        qc_rows.append('<tr>' + ''.join('<td>' + html.escape('Unavailable' if v is None else str(v)) + '</td>' for v in values) + '<td><a href="' + quote(q['sample'], safe='') + '/qc/' + quote(q['sample'], safe='') + '.index.html">QC report</a></td></tr>')
    warning_rows = ''.join('<p><strong>' + html.escape(q['sample']) + '</strong>: ' + html.escape(w) + '</p>' for q in data.get('qc', []) for w in q.get('warnings', []))
    qc_table = '<h2>Sample QC</h2><table><tr><th>Sample</th><th>Primary reads</th><th>Alignment rate</th><th>On-enrichment fraction</th><th>CpGs detected</th><th>Report</th></tr>' + ''.join(qc_rows) + '</table>' if qc_rows else ''
    sample_links='<h2>Sample summaries</h2>'+''.join('<p><a href="'+quote(p,safe='/')+'">'+html.escape(row['sample'])+' — open summary</a></p>' for row in data['analyses'] if row.get('analysis')=='summary' for p in row.get('files',[]) if p.endswith('.html'))
    return '<!doctype html><meta charset="utf-8"><title>FrankONTstein results</title><style>'+CSS+'</style><h1>FrankONTstein results</h1>'+sample_links+'<p>Caller results are retained separately; sample summaries include NASVAR-focused two-caller somatic consensus when available. See manifest.json and pipeline_info for provenance and execution status.</p><table><tr><th>Sample</th><th>Analysis</th><th>Status</th><th>Files</th></tr>' + ''.join(rows) + '</table>' + qc_table + '<h2>Review warnings</h2>' + warning_rows + '<p>Check each caller’s filtering/provenance and quality-warning files. PASS subsets retain only exact PASS records; dot means unassessed. NASVAR/CNV estimates require evidence review, not consensus interpretation.</p>'

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
            data['qc'].append({'sample': q['sample'], 'warnings': q.get('warnings', []), 'alignment': {k:a.get(k) for k in ['counts','alignment_rate','on_enrichment_fraction_mapped']},
                'methylation': {'genome': {'combined': {'sites': q.get('methylation', {}).get('genome', {}).get('combined', {}).get('sites')}}}})
    Path('manifest.json').write_text(json.dumps(data, indent=2))
    Path('index.html').write_text(render(data))
