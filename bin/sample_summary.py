#!/usr/bin/env python3
"""Prepare escaped, offline Quarto content from small sample-scoped work artifacts."""
import argparse
import csv
import html
import json
from pathlib import Path
import re


def read_one(root, pattern):
    paths=sorted(Path(root).rglob(pattern))
    if len(paths)>1: raise ValueError('Ambiguous summary input: '+pattern)
    return json.loads(paths[0].read_text()) if paths else None


def load(sample, root, context):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',sample):raise ValueError('Unsafe sample identifier')
    classy=read_one(root,'*_combined_classification.json')
    qc=read_one(root,'*metrics.json')
    if qc:
        def bounded(value):
            if isinstance(value,dict):return {k:bounded(v) for k,v in value.items() if 'hist' not in k and k!='contigs'}
            if isinstance(value,list):return [bounded(v) for v in value]
            return value
        qc=bounded(qc)
    nasvar=read_one(root,sample+'.result.json')
    config=read_one(root,sample+'.pipeline_config.json')
    warnings=read_one(root,'*quality_warnings.json')
    consensus=read_one(root,'*.consensus.json')
    for obj,key in [(classy,'sample_label'),(qc,'sample'),(consensus,'sample')]:
        if obj and obj.get(key) and obj[key]!=sample: raise ValueError('Summary sample identity mismatch')
    classifiers=[]
    for path in sorted(Path(root).rglob('*combined_top_calls.tsv')):
        with path.open() as f:
            classifiers += [dict(r) for r in csv.DictReader(f,delimiter='\t')
                            if r.get('classifier_domain')=='blood' and r.get('classification_task')=='cancer_classification']
    # Current Classy top-call tables are authoritative. Fall back to MARLIN JSON for older exports.
    if not classifiers and classy:
        marlin=classy.get('marlin') or classy
        for rank,row in enumerate(marlin.get('inference',{}).get('annotated_probabilities',[])[:3],1):
            score=row.get('probability'); cutoff=marlin.get('cutoff')
            classifiers.append(dict(source_label='MARLIN',rank=rank,display_label=row.get('class_name'),score=score,
                                    cutoff=cutoff,passed_cutoff=None if score is None or cutoff is None else score>=cutoff,
                                    **{k:marlin.get('target_coverage',{}).get(k) for k in ['observed_feature_count','model_feature_count','observed_target_fraction']}))
    fusion=[]
    for entry in (nasvar or {}).get('fusions',{}).get('fusions',[]): fusion.append(dict(source='NASVAR',evidence=entry))
    for path in sorted(Path(root).rglob('*.tsv')):
        if 'combined_top_calls' in path.name:continue
        # Only Stellerator TSVs are selected into this input directory by SummaryInputs.
        with path.open() as f:
            for row in csv.DictReader(f,delimiter='\t'):fusion.append(dict(source='Stellerator',evidence=dict(row)))
    pgx_names=(config or {}).get('genes',{}).get('snv',{}).get('pharmacogenomics',[])
    pgx={g:(nasvar or {}).get('snv',{}).get('genes',{}).get(g) for g in pgx_names}
    callers=context['plan']['callers']
    for analysis,value in [('nasvar',nasvar),('qc',qc),('methylation',classy)]:
        if analysis in context.get('analyses',[]) and value is None:
            raise ValueError('Completed analysis missing its summary input: '+analysis)
    if nasvar and context['plan']['tier']=='tertiary' and 'nasvar' in context.get('analyses',[]) and config is None:
        raise ValueError('NASVAR pipeline configuration missing for pharmacogenomic categorization')
    if consensus is None:
        available=all(c in callers for c in ('deepsomatic','clairsto'))
        if available and not context.get('validation_preview'):raise ValueError('Required consensus result missing')
        consensus=dict(status='unavailable',reason='Validation preview: reference assets unavailable; consensus has not been computed' if available else 'Both DeepSomatic and ClairS-TO must be selected on a compatible genome',counts=None,queries=[],evidence=[])
    statuses={a:'completed' for a in context.get('analyses',[])}
    for a in ['qc','nasvar','stellerator','methylation']:
        statuses.setdefault(a,'not_assessed')
    if context.get('disable_qc'):statuses['qc']='disabled'
    return dict(schema_version=1,validation_preview=bool(context.get('validation_preview')),sample=sample,run_id=context.get('run_id'),session_id=context.get('session_id'),
                genome=context['plan']['genome'],tier=context['plan']['tier'],callers=callers,analyses=statuses,
                classification=dict(status='completed' if classifiers else 'unavailable',models=classifiers),
                qc=qc,consensus=consensus,nasvar=nasvar,quality_warnings=warnings,pharmacogenomics=pgx,
                fusions=dict(status='evidence_only',consensus_status='not_assessed',candidates=fusion),
                provenance=context.get('images',{}))


def cell(v):
    if v is None:return 'Not available'
    if isinstance(v,(dict,list,tuple)):v=json.dumps(v,ensure_ascii=False,sort_keys=True)
    return html.escape(str(v),quote=True)


def table(headers,rows):
    if not rows:return '<p>Not assessed or no reported records; see section status.</p>'
    return '<table><thead><tr>'+''.join('<th>'+cell(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+cell(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'


def render(data,template):
    c=data['consensus'];sections=[]
    sections.append('<h1>'+cell(data['sample'])+'</h1>')
    if data.get('validation_preview'):sections.append('<div class="notice">Validation preview: existing analysis results only; consensus has not been computed.</div>')
    sections.append(table(['Run','Genome','Tier','Selected callers'],[[data['run_id'],data['genome'],data['tier'],data['callers']]]))
    sections.append('## Analysis status\n\n'+table(['Analysis','Status'],sorted(data['analyses'].items())))
    sections.append('## Blood tumor classification\n\n<p>Model results are shown separately; scores are not pooled into a diagnosis. Below-cutoff and control classifications remain visible.</p>')
    sections.append(table(['Model','Rank','Class','Score','Cutoff','Above cutoff','Observed features','Model features','Observed target fraction'],[
        [r.get(k) for k in ['source_label','rank','display_label','score','cutoff','passed_cutoff','observed_feature_count','model_feature_count','observed_target_fraction']] for r in data['classification']['models']]))
    sections.append('## Quality control')
    qc=data['qc'] or {};alignment=qc.get('alignment',{});coverage=alignment.get('coverage',{})
    sections.append(table(['Metric','Value'],[['Primary reads',alignment.get('counts',{}).get('primary_reads')],['Alignment rate',alignment.get('alignment_rate')]]))
    sections.append(table(['MAPQ','Region','Mean depth','Breadth ≥1x','Breadth ≥20x'],[
        [mq,scope,stats.get('mean'),stats.get('breadth',{}).get('1'),stats.get('breadth',{}).get('20')]
        for mq in ['0','20'] for scope,stats in coverage.get(mq,{}).items() if scope in ['genome','enrichment','off_enrichment','targets']]))
    methyl=qc.get('methylation',{})
    sections.append(table(['Methylation scope','Modification','Sites'],[[scope,mod,stats.get('sites')] for scope,mods in methyl.items() if isinstance(mods,dict) for mod,stats in mods.items() if isinstance(stats,dict)]))
    warnings=list(qc.get('warnings',[]))+(data['quality_warnings'] or {}).get('warnings',[])+(data['quality_warnings'] or {}).get('limitations',[])
    sections.append(table(['Review warnings'],[[w] for w in warnings]))
    sections.append('## Somatic consensus\n\n<div class="notice">Tumor-only somatic candidates: exact normalized allele and PASS agreement between DeepSomatic and ClairS-TO. Agreement does not prove somatic origin. No consensus detected is not a confident reference call.</div>')
    reason = c.get('reason')
    if not reason and c['status'] == 'completed':
        if any((c.get('counts') or {}).values()):
            reason = 'PASS agreement at configured NASVAR queries.'
        elif not c.get('evidence'):
            reason = 'No eligible variant records at the configured NASVAR query positions/windows.'
        else:
            reason = 'No allele passed both somatic callers at the configured NASVAR queries.'
    sections.append('<p>Counts cover only NASVAR pathogenic SNV query positions and indel windows, not all target regions. Pharmacogenomic findings are separate.</p>')
    sections.append(table(['Status','SNVs','Indels','Reason'],[[c['status'],(c.get('counts') or {}).get('snv'),(c.get('counts') or {}).get('indel'),reason]]))
    evidence=c.get('evidence',[]);nasgenes=(data['nasvar'] or {}).get('snv',{}).get('genes',{});itdgenes=(data['nasvar'] or {}).get('itd',{}).get('genes',{})
    qrows=[]
    for q in c.get('queries',[]):
        found=[r for r in evidence if q in r['queries']]
        qrows.append([q['gene'],q['label'],q.get('transcript'),f"{q['chrom']}:{q['start']+1}-{q['end']}",
                      'consensus' if any(r['status']=='consensus' for r in found) else 'no_consensus_detected',
                      found,nasgenes.get(q['gene']) if q['kind']=='snv' else itdgenes.get(q['gene'])])
    sections.append('### NASVAR query review\n\n<p>Query labels identify the configured locus, not an inferred protein effect. NASVAR support and thresholds remain separate from caller PASS decisions.</p>\n\n'+table(['Gene','Query','Transcript','Locus (1-based)','Status','Caller evidence','NASVAR evidence'],qrows))
    sections.append('## Pharmacogenomics\n\n<p>NASVAR-reported findings, excluded from somatic consensus. No new star-allele inference.</p>\n\n'+table(['Gene','NASVAR result'],sorted(data['pharmacogenomics'].items())))
    sections.append('## Fusion evidence\n\n<p>Evidence only; fusion consensus was not assessed. Rows from different callers are not presumed to describe the same event.</p>\n\n'+table(['Source','Candidate evidence'],[[r['source'],r['evidence']] for r in data['fusions']['candidates']]))
    sections.append('## Provenance\n\n'+table(['Component','Image'],sorted(data['provenance'].items())))
    # Raw HTML blocks preserve escaping even for Markdown-sensitive sample names.
    return Path(template).read_text().replace('<!-- SUMMARY_CONTENT -->','\n\n'.join(sections))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['sample','inputs','context','template']:p.add_argument('--'+name,required=True)
    p.add_argument('--output',default='summary');a=p.parse_args()
    data=load(a.sample,a.inputs,json.loads(Path(a.context).read_text()))
    out=Path(a.output);out.mkdir(exist_ok=True,parents=True)
    (out/(a.sample+'.summary.json')).write_text(json.dumps(data,indent=2)+'\n')
    (out/(a.sample+'.summary.qmd')).write_text(render(data,a.template))
