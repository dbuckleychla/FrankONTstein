#!/usr/bin/env python3
"""Prepare escaped, offline Quarto content from small sample-scoped work artifacts."""
import argparse
import csv
import html
import json
from pathlib import Path
import re
from report_presentation import CSS, qc_content, number, display, table as presentation_table, esc
import base64


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
            if isinstance(value,dict):return {k:bounded(v) for k,v in value.items() if k!='contigs'}
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
    statuses.update(context.get('analysis_status',{}))
    for a in ['qc','nasvar','stellerator','methylation']:
        statuses.setdefault(a,'not_assessed')
    if context.get('disable_qc'):statuses['qc']='disabled'
    return dict(schema_version=1,validation_preview=bool(context.get('validation_preview')),sample=sample,run_id=context.get('run_id'),session_id=context.get('session_id'),
                genome=context['plan']['genome'],tier=context['plan']['tier'],callers=callers,analyses=statuses,
                classification=dict(status='completed' if classifiers else 'unavailable',models=classifiers),
                qc=qc,consensus=consensus,nasvar=nasvar,quality_warnings=warnings,pharmacogenomics=pgx,
                fusions=dict(status='evidence_only',consensus_status='not_assessed',candidates=fusion),
                exclusions=context['plan'].get('skipped',[]), provenance=context.get('images',{}), figures=[dict(name=p.name, data=base64.b64encode(p.read_bytes()).decode()) for p in sorted(Path(root).rglob('*.svg')) if p.name.startswith(sample+'.') and '.gc_vs_coverage' not in p.name and p.stat().st_size <= 5_000_000])


def cell(v):
    return esc(display(v))


def table(headers,rows):
    if not rows:return '<p>Not assessed or no reported records; see section status.</p>'
    return presentation_table(headers, rows)


def fusion_summary_row(candidate):
    """Use caller-reported totals; never sum breakpoint counts or combine callers."""
    e=candidate['evidence']; source=candidate['source']
    if source=='NASVAR':
        a=e.get('gene1',{}); b=e.get('gene2',{})
        gene1=a.get('name'); gene2=b.get('name')
        chr1,pos1=a.get('chr'),a.get('pos');chr2,pos2=b.get('chr'),b.get('pos')
        support=e.get('supporting_reads')
    else:
        # TSV adapters only expose explicit fields; unknown schemas retain native details.
        fields={re.sub(r'[^a-z0-9]','',k.lower()):v for k,v in e.items()}
        def get(*keys):
            return next((fields[k] for k in keys if fields.get(k) not in (None,'')),None)
        gene1=get('gene1','gene1name','geneaname','genea');gene2=get('gene2','gene2name','genebname','geneb')
        chr1=get('chr1','chrom1','chromosome1','gene1chr');pos1=get('pos1','position1','breakpoint1','gene1pos')
        chr2=get('chr2','chrom2','chromosome2','gene2chr');pos2=get('pos2','position2','breakpoint2','gene2pos')
        support=get('totalsupportingreads','supportingreads','readsupport','support','nreads')
    coords=lambda chrom,pos: f'{chrom}:{pos}' if chrom is not None and pos is not None else None
    name=f'{gene1}::{gene2}' if gene1 and gene2 else None
    try: support=int(support) if support is not None else None
    except (ValueError,TypeError): pass
    return [source,name,coords(chr1,pos1),coords(chr2,pos2),support]


def fusion_table(data):
    candidates=data['fusions']['candidates']
    result=presentation_table(['Caller','Fusion','Gene 1 coordinates (native)','Gene 2 coordinates (native)','Total supporting reads'],
        [fusion_summary_row(r) for r in candidates],
        empty='No NASVAR fusion candidates reported (completed).' if 'fusions' in (data.get('nasvar') or {}) else 'Fusion analysis unavailable.')
    result+='<p>Supporting-read totals are caller-reported per event. Breakpoint counts are not added, and evidence is not combined across callers. Coordinates retain the caller’s convention.</p>'
    others=[r['evidence'] for r in candidates if r['source']!='NASVAR']
    if others:
        keys=sorted({k for r in others for k in r})
        result+='<details><summary>Stellerator evidence · native fields</summary>'+presentation_table(keys,[[r.get(k) for k in keys] for r in others])+'</details>'
    return result


def nasvar_sections(data):
    n=data.get('nasvar') or {};s=['## NASVAR copy number and karyotype\n']
    if not n: return s[0]+'<p>NASVAR unavailable; see analysis status.</p>'
    k=n.get('karyotype')
    if k is None: s.append('<p>Karyotype unavailable.</p>')
    else:
        s.append('<p>NASVAR estimates; coverage-derived karyotype and blast ratio are not validated clinical classifications. Review allelic evidence and quality warnings.</p>')
        s.append(presentation_table(['Metric','NASVAR estimate'],[[label,k.get(key)] for key,label in [('karyotype_string','Coverage karyotype'),('iscn_string','ISCN string'),('blast_ratio','Blast ratio (fraction)'),('within_segment_spread','Within-segment spread')]]))
        regions=sorted(set(k.get('karyotype',{}))|set(k.get('medians',{})))
        s.append('<details><summary>Chromosome / arm estimates</summary>'+presentation_table(['Region','Karyotype estimate','Median'],[[r,k.get('karyotype',{}).get(r),k.get('medians',{}).get(r)] for r in regions])+'</details>')
    s.append('<h3>Gene copy-number estimates</h3>'+presentation_table(['Gene','Focal copy number','Local copy number'],[[gene,v.get('focal'),v.get('local')] for gene,v in sorted(n.get('cnv',{}).get('genes',{}).items())],empty='CNV unavailable.' if 'cnv' not in n else 'No gene estimates reported.'))
    events=[]
    for gene,v in sorted(n.get('cnv',{}).get('genes',{}).items()):
        for kind in ['deletions','duplications']:
            for event in v.get(kind) or []:
                events.append([gene,kind,event.get('chrom'),event.get('start'),event.get('end'),event.get('reads')])
    if events: s.append(presentation_table(['Gene','CNV evidence','Chromosome','Start (native)','End (native)','Reads'],events))
    for f in data.get('figures',[]):
        if '.gc_vs_coverage' in f['name']: continue
        title=f['name'].removeprefix(data['sample']+'.').removesuffix('.svg').replace('.', ' · ').replace('_',' ')
        s.append('<figure><h3>'+esc(title)+'</h3><img alt="'+esc(title)+'" src="data:image/svg+xml;base64,'+f['data']+'"><figcaption>NASVAR '+esc(title)+'</figcaption></figure>')
    for kind,title in [('snv','NASVAR SNV evidence'),('itd','NASVAR indel evidence')]:
        if kind not in n: continue
        s.append('### '+title+'\n')
        genes=n[kind].get('genes',{})
        if kind=='snv':
            pgx=set(data.get('pharmacogenomics',{}))
            s.append(presentation_table(['Gene','Genotype','Coverage','Amino-acid changes','Mutation','Evidence'],[[gene,v.get('genotype'),number(v.get('coverage'),1),v.get('aa_changes'),mutation,result] for gene,v in sorted(genes.items()) if gene not in pgx for mutation,result in (v.get('mutations') or {'None reported':None}).items()]))
        else:
            s.append(presentation_table(['Gene','Chromosome','Position (native)','Length (bp)','Merged','Coverage'],[[gene]+[event.get(k) for k in ['chrom','position','length','merged','coverage']] for gene,events in sorted(genes.items()) for event in events]))
    s.append('### Breakpoint sequence evidence\n')
    points=n.get('breakpoint_consensus',{}).get('breakpoints',[])
    s.append(presentation_table(['Gene 1','Chr 1','Position 1 (native)','Gene 2','Chr 2','Position 2 (native)','Reads','Mean coverage'],[[v.get(k) for k in ['gene0_name','gene0_chr','gene0_pos','gene1_name','gene1_chr','gene1_pos','n_reads','mean_coverage']] for v in points],empty='No breakpoint sequence records reported.' if 'fusions' in n else 'Breakpoint analysis unavailable.'))
    for v in points:
        s.append('<details><summary>Breakpoint sequence: '+esc(v.get('gene0_name'))+' / '+esc(v.get('gene1_name'))+'</summary><pre>'+esc(v.get('bracketed_sequence',v.get('consensus_sequence','Unavailable')))+'</pre></details>')
    sample=data['sample']
    s.append('<p><a href="../nasvar/'+sample+'.result.json">NASVAR raw results</a> · <a href="../nasvar/'+sample+'.report.html">Original NASVAR report</a></p>')
    return '\n\n'.join(s)


def render(data,template):
    c=data['consensus'];sections=[]
    sections.append('<h1>'+cell(data['sample'])+'</h1>')
    if data.get('validation_preview'):sections.append('<div class="notice">Validation preview: existing analysis results only; consensus has not been computed.</div>')
    sections.append(table(['Run','Genome','Tier','Selected callers'],[[data['run_id'],data['genome'],data['tier'],data['callers']]]))
    sections.append('## Analysis status\n\n'+table(['Analysis','Status'],sorted(data['analyses'].items())))
    if data.get('exclusions'): sections.append(presentation_table(['Excluded analysis','Reason'],[[r.get('caller'),r.get('reason')] for r in data['exclusions']]))
    sections.append('## Blood tumor classification\n\n<p>Model results are shown separately; scores are not pooled into a diagnosis. Below-cutoff and control classifications remain visible.</p>')
    sections.append(presentation_table(['Model','Rank','Class','Score','Cutoff','Above cutoff','Observed features','Model features','Observed target fraction'],[
        [number(r.get(k),percent=True) if k=='observed_target_fraction' else r.get(k) for k in ['source_label','rank','display_label','score','cutoff','passed_cutoff','observed_feature_count','model_feature_count','observed_target_fraction']] for r in data['classification']['models']],empty='Classification results unavailable.'))
    qc=data['qc'] or {}
    warnings=list(qc.get('warnings',[]))+(data['quality_warnings'] or {}).get('warnings',[])+(data['quality_warnings'] or {}).get('limitations',[])
    sections.insert(3, '## Review warnings\n\n'+presentation_table(['Review warnings'],[[w] for w in warnings],empty='No recorded warnings.'))
    sections.append('## Fusion summary\n\n<p>Evidence only; fusion consensus was not assessed. Rows from different callers are not presumed to describe the same event.</p>\n\n'+fusion_table(data))
    sections.append(nasvar_sections(data))
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
                      len(found)])
    sections.append('### NASVAR query review\n\n<p>Query labels identify the configured locus, not an inferred protein effect. NASVAR support and thresholds remain separate from caller PASS decisions.</p>\n\n'+table(['Gene','Query','Transcript','Locus (1-based)','Status','Allele records'],qrows))
    erows=[]
    for allele in evidence:
        for caller,records in allele.get('evidence',{}).items():
            for ev in records:
                erows.append([allele.get('chrom'),allele.get('pos'),allele.get('ref'),allele.get('alt'),allele.get('status'),caller,ev.get('filter'),ev.get('DP'),ev.get('AD'),ev.get('AF',ev.get('VAF')),ev.get('GT')])
    sections.append(presentation_table(['Chromosome','Position (1-based)','REF','ALT','Agreement','Caller','FILTER','Depth','Allele depths','Allele fraction','Genotype'],erows,empty='No eligible caller evidence records; see consensus status.'))
    sections.append('## Pharmacogenomics\n\n<p>NASVAR-reported findings, excluded from somatic consensus. No new star-allele inference.</p>\n\n'+presentation_table(['Gene','Genotype','Coverage','Amino-acid changes','Mutations'],[[g,(v or {}).get('genotype'),number((v or {}).get('coverage'),1),(v or {}).get('aa_changes'),(v or {}).get('mutations')] for g,v in sorted(data['pharmacogenomics'].items())],empty='Pharmacogenomics not assessed or unavailable; see configured analyses.'))
    sections.append('## Quality control')
    sections.append(qc_content(qc) if qc else '<p>QC '+cell(data['analyses'].get('qc','unavailable'))+'</p>')
    sections.append('## Provenance\n\n'+table(['Component','Image'],sorted(data['provenance'].items())))
    # Raw HTML blocks preserve escaping even for Markdown-sensitive sample names.
    return Path(template).read_text().replace('<!-- SUMMARY_CONTENT -->','<style>'+CSS+'</style>\n\n'+'\n\n'.join(sections))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['sample','inputs','context','template']:p.add_argument('--'+name,required=True)
    p.add_argument('--output',default='summary');a=p.parse_args()
    data=load(a.sample,a.inputs,json.loads(Path(a.context).read_text()))
    out=Path(a.output);out.mkdir(exist_ok=True,parents=True)
    (out/(a.sample+'.summary.json')).write_text(json.dumps(data,indent=2)+'\n')
    (out/(a.sample+'.summary.qmd')).write_text(render(data,a.template))
