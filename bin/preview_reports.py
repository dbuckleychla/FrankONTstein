#!/usr/bin/env python3
"""Render separate report previews from published small artifacts; never edit source runs."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from sample_summary import load, render
from adaptive_qc import render_report
from make_report import render as render_index


def preview(source, output, template, lengths=None, renderer='quarto'):
    source=Path(source).resolve(); output=Path(output).resolve()
    if output==source or source in output.parents: raise ValueError('Preview must be outside original run')
    output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((source/'manifest.json').read_text())
    records=[]
    samples=sorted({r['sample'] for r in manifest['analyses']})
    if lengths and len(samples)!=1: raise ValueError('A length audit requires a singleton run')
    for sample in samples:
        with tempfile.TemporaryDirectory(prefix='report-inputs-') as tmp:
            inputs=Path(tmp)
            for analysis,patterns in {'nasvar':['*.json','*.svg','*.report.html','*.report.md'], 'methylation':['*_combined_classification.json','*combined_top_calls.tsv','*.artifact_audit.txt','*.artifact_audit.json'], 'qc':['*.metrics.json']}.items():
                for pattern in patterns:
                    for p in (source/sample/analysis).rglob(pattern):
                        if p.stat().st_size>20_000_000: continue
                        if p.name.endswith(('.json','.svg','.tsv')): shutil.copy2(p,inputs/p.name)
                        dest=output/p.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
            metric=next(inputs.glob('*.metrics.json'),None)
            qc=json.loads(metric.read_text()) if metric else None
            if qc and lengths:
                updated=json.loads(Path(lengths).read_text())
                for key in ['all','mapped','unmapped','on_enrichment','off_enrichment']:
                    if updated['read_lengths'][key]!=qc['alignment']['read_lengths'][key]: raise ValueError('Existing length metrics differ: '+key)
                qc['alignment']['read_lengths']=updated['read_lengths'];qc['schema_version']=2
                qc['preview_length_assets']=updated['assets']
            elif qc:
                qc.setdefault('warnings',[]).append('Target read lengths unavailable in this legacy output; a focused BAM audit is required.')
            if qc:
                metric.write_text(json.dumps(qc,indent=2))
                qdir=output/sample/'qc';qdir.mkdir(parents=True,exist_ok=True)
                (qdir/(sample+'.metrics.json')).write_text(json.dumps(qc,indent=2))
                (qdir/(sample+'.index.html')).write_text(render_report(qc))
            context=copy.deepcopy(manifest['run']);context['analyses']=[r['analysis'] for r in manifest['analyses'] if r['sample']==sample and r['status']=='completed' and r['analysis']!='summary']
            context['analysis_status']={r['analysis']:r['status'] for r in manifest['analyses'] if r['sample']==sample and r['analysis']!='summary'}
            context['run_id']=context.get('parameters',{}).get('run_id');context['validation_preview']=True
            data=load(sample,inputs,context)
            dest=output/sample/'summary';dest.mkdir(parents=True,exist_ok=True)
            qmd=dest/(sample+'.summary.qmd');qmd.write_text(render(data,template))
            (dest/(sample+'.summary.json')).write_text(json.dumps(data,indent=2))
            if renderer=='quarto': subprocess.run(['quarto','render',str(qmd),'--to','html'],check=True)
            else:
                subprocess.run([renderer,str(qmd),'--from','markdown+raw_html','--to','html5','--standalone','--toc','--embed-resources','-o',str(qmd.with_suffix('.html'))],check=True)
            for analysis in ['summary','qc','nasvar','methylation']:
                files=[str(p.relative_to(output)) for p in sorted((output/sample/analysis).rglob('*')) if p.is_file()]
                if files: records.append(dict(sample=sample,analysis=analysis,status='completed',files=files))
    manifest['analyses']=records;manifest['preview']={'source':str(source),'renderer':renderer,'scientific_reruns':'read lengths only' if lengths else 'none'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (output/'index.html').write_text(render_index(manifest))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source');p.add_argument('output');p.add_argument('--lengths');p.add_argument('--renderer',default='quarto');p.add_argument('--template',default=str(Path(__file__).resolve().parents[1]/'assets/summary/template.qmd'))
    a=p.parse_args();preview(a.source,a.output,a.template,a.lengths,a.renderer)
