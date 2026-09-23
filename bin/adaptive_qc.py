#!/usr/bin/env python3
"""Bounded, contig-parallel QC. No per-read database or per-base output files."""
import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import html
import itertools
import json
import multiprocessing
from pathlib import Path
import re
import subprocess
import sys
import pysam


class Regions:
    def __init__(self, rows):
        self.rows = sorted(rows)
        self.starts = [r[0] for r in self.rows]
        self.maxends = []
        end = 0
        for r in self.rows:
            end = max(end, r[1]); self.maxends.append(end)

    def hits(self, start, end):
        i = bisect_left(self.starts, end) - 1
        while i >= 0 and self.maxends[i] > start:
            if self.rows[i][1] > start:
                yield self.rows[i]
            i -= 1

    def contains(self, pos):
        return next(self.hits(pos, pos + 1), None) is not None


def merged(rows):
    out = []
    for start, end, *_ in sorted(rows):
        if out and start <= out[-1][1]:
            out[-1][1] = max(end, out[-1][1])
        else:
            out.append([start, end])
    return out


def read_bed(path, lengths):
    rows = defaultdict(list)
    with open(path) as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip() or line.startswith(('#', 'track', 'browser')): continue
            f = line.rstrip().split('\t'); start, end = int(f[1]), int(f[2])
            if f[0] not in lengths or not 0 <= start < end <= lengths[f[0]]:
                raise ValueError(f'{path}:{line_no}: invalid BED interval')
            rows[f[0]].append((start, end, f'{line_no}:{f[3] if len(f)>3 else f[0]+":"+f[1]+"-"+f[2]}'))
    return dict(rows)


def lengths_summary(counts):
    counts = Counter({int(k): v for k, v in counts.items()})
    n = sum(counts.values()); bases = sum(k*v for k,v in counts.items())
    if not n: return dict(reads=0, bases=0, mean=None, median=None, n50=None, histogram={})
    ranks = [(n-1)//2, n//2]; vals = []; total = 0
    for length, count in sorted(counts.items()):
        vals.extend(length for rank in ranks if total <= rank < total + count)
        total += count
    acc = 0; n50 = 0
    for length, count in sorted(counts.items(), reverse=True):
        acc += length * count
        if acc >= bases/2: n50 = length; break
    # Plot bins only; exact statistics use the length-frequency table.
    hist = Counter()
    for length, count in counts.items(): hist[(length//100)*100] += count
    return dict(reads=n, bases=bases, mean=bases/n, median=sum(vals)/2, n50=n50, histogram=dict(hist))


def depth_summary(hist, size):
    hist = Counter(hist)
    hist[0] += size - sum(hist.values())
    if hist[0] < 0: raise ValueError('Coverage denominator smaller than observed positions')
    return dict(bases=size, aligned_bases=sum(k*v for k,v in hist.items()),
                mean=sum(k*v for k,v in hist.items())/size if size else None,
                breadth={str(t):sum(v for k,v in hist.items() if k >= t)/size if size else None for t in [1,5,10,20]},
                histogram=dict(sorted(hist.items())))


def primary_contig(chrom):
    # UCSC, bare chromosome and RefSeq accessions for human primary chromosomes.
    if re.fullmatch(r'(chr)?([1-9]|1[0-9]|2[0-2]|X|Y)', chrom): return True
    match = re.fullmatch(r'NC_0*(\d+)\.\d+', chrom)
    return bool(match and (1 <= int(match[1]) <= 24 or 60925 <= int(match[1]) <= 60948))


def contig_qc(job):
    bam_path, chrom, size, erows, trows = job
    e = Regions(merged(erows)); t = Regions(merged(trows)); targets = Regions(trows)
    groups = defaultdict(Counter); counts = Counter(); mapq = Counter()
    with pysam.AlignmentFile(bam_path, 'rb') as bam:
        for read in bam.fetch(chrom):
            if read.is_secondary: counts['secondary'] += 1; continue
            if read.is_supplementary: counts['supplementary'] += 1; continue
            if read.is_unmapped:
                length = read.query_length or read.infer_query_length() or 0
                groups['all'][length] += 1; groups['unmapped'][length] += 1
                continue
            counts['mapped_primary'] += 1
            counts['qc_failed_primary'] += int(read.is_qcfail)
            counts['duplicate_flagged_primary'] += int(read.is_duplicate)
            length = read.query_length or read.infer_query_length() or 0
            on = any(next(e.hits(a,b), None) is not None for a,b in read.get_blocks())
            for key in ['all','mapped', 'on_enrichment' if on else 'off_enrichment']:
                groups[key][length] += 1
            mapq[read.mapping_quality] += 1
    sizes = {'genome': size, 'enrichment':sum(b-a for a,b in e.rows),
             'targets':sum(b-a for a,b in t.rows)}
    sizes['off_enrichment'] = size - sizes['enrichment']
    coverage = {}; per_target = {}
    # Separate MAPQ passes; never materialize depth output. Parallelism is across contigs.
    for threshold in [0,20]:
        hist = {key:Counter() for key in sizes}; thist = {r[2]:[0,0,0,0,0] for r in trows}
        cmd = ['samtools','depth','-r',chrom,'-q','0','-Q',str(threshold),
               '-g','0x600','-G','0x900',bam_path]
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True) as proc:
            for line in proc.stdout:
                _, pos, depth = line.split(); pos = int(pos)-1; depth = int(depth)
                if depth == 0: continue
                hist['genome'][depth] += 1
                hist['enrichment' if e.contains(pos) else 'off_enrichment'][depth] += 1
                if t.contains(pos): hist['targets'][depth] += 1
                for row in targets.hits(pos,pos+1):
                    acc=thist[row[2]]; acc[0]+=depth
                    for idx,cutoff in enumerate([1,5,10,20],1): acc[idx]+=int(depth>=cutoff)
            if proc.wait(): raise RuntimeError(f'samtools depth failed for {chrom}, MAPQ {threshold}')
        coverage[str(threshold)] = {k:depth_summary(hist[k],v) for k,v in sizes.items()}
        per_target[str(threshold)] = {r[2]:dict(chrom=chrom,start=r[0],end=r[1],bases=r[1]-r[0],
            aligned_bases=thist[r[2]][0],mean=thist[r[2]][0]/(r[1]-r[0]),
            breadth={str(t):thist[r[2]][i]/(r[1]-r[0]) for i,t in enumerate([1,5,10,20],1)}) for r in trows}
    return dict(chrom=chrom, counts=dict(counts), lengths=dict(groups), mapq=dict(mapq), coverage=coverage, targets=per_target)


def bam_qc(bam, fasta, enrichment, targets, threads):
    with pysam.FastaFile(fasta) as ref: sizes = dict(zip(ref.references,ref.lengths))
    erows = read_bed(enrichment,sizes); trows = read_bed(targets,sizes)
    with pysam.AlignmentFile(bam,'rb') as handle:
        bam_sizes = dict(zip(handle.references,handle.lengths))
    if bam_sizes != sizes: raise ValueError('BAM/FASTA contig mismatch')
    jobs = [(bam,c,s,erows.get(c,[]),trows.get(c,[])) for c,s in bam_sizes.items()]
    results = []
    with ProcessPoolExecutor(max_workers=max(1,threads//2), mp_context=multiprocessing.get_context('spawn')) as pool:
        # One Python worker + its depth subprocess per slot; payloads contain no reads.
        for result in pool.map(contig_qc,jobs): results.append(result)
    counts=Counter(); groups=defaultdict(Counter); mapq=Counter()
    for r in results:
        counts.update(r['counts']); mapq.update(r['mapq'])
        for k,v in r['lengths'].items(): groups[k].update(v)
    with pysam.AlignmentFile(bam,'rb') as handle:
        for read in handle.fetch('*'):
            if read.is_secondary or read.is_supplementary: continue
            n=read.query_length or read.infer_query_length() or 0
            groups['all'][n]+=1; groups['unmapped'][n]+=1
    stats={k:lengths_summary(groups[k]) for k in ['all','mapped','unmapped','on_enrichment','off_enrichment']}
    counts['primary_reads']=stats['all']['reads']; counts['unmapped_primary']=stats['unmapped']['reads']
    mapped=counts['mapped_primary']; total=counts['primary_reads']; on=stats['on_enrichment']['reads']
    coverage={}
    for threshold in ['0','20']:
        coverage[threshold]={}
        for scope in ['genome','enrichment','targets','off_enrichment']:
            selected=[r for r in results if primary_contig(r['chrom'])]
            h=Counter(); size=0
            for r in selected:
                d=r['coverage'][threshold][scope]; h.update(d['histogram']); size+=d['bases']
            coverage[threshold][scope]=depth_summary(h,size)
        a=coverage[threshold]['enrichment']['mean']; b=coverage[threshold]['off_enrichment']['mean']
        coverage[threshold]['enrichment_depth_ratio']=a/b if a is not None and b else None
    for r in results:
        r.pop('lengths',None); r.pop('mapq',None)
    return dict(counts=dict(counts),read_lengths=stats,mapq=dict(mapq),
                alignment_rate=mapped/total if total else None,
                on_enrichment_fraction_mapped=on/mapped if mapped else None,
                on_enrichment_fraction_all=on/total if total else None,
                coverage=coverage,contigs=results)


def mod_stats():
    return dict(sites=0,depth_hist=Counter(), modified=0,valid=0,beta_sum=0.,beta_hist=Counter(),beta_hist_depth10=Counter())


def methylation_qc(bed, fasta, enrichment, targets, contig=None):
    with pysam.FastaFile(fasta) as ref: sizes=dict(zip(ref.references,ref.lengths))
    ers=read_bed(enrichment,sizes); trs=read_bed(targets,sizes)
    er={c:Regions(merged(r)) for c,r in ers.items()}; tr={c:Regions(merged(r)) for c,r in trs.items()}
    def scopes(c,p):
        out=['genome' if primary_contig(c) else 'other_contigs']
        if primary_contig(c) and c in er and er[c].contains(p): out.append('enrichment')
        if primary_contig(c) and c in tr and tr[c].contains(p): out.append('targets')
        return out
    denominators=Counter()
    with pysam.FastaFile(fasta) as ref:
        for chrom,size in sizes.items():
            if contig is not None and chrom != contig: continue
            for start in range(0,size,1000000):
                seq=ref.fetch(chrom,start,min(start+1000001,size)).upper()
                for match in re.finditer('CG',seq):
                    for scope in scopes(chrom,start+match.start()): denominators[scope]+=1
    metrics={s:{m:mod_stats() for m in ['combined','5mC','5hmC']} for s in ['genome','other_contigs','enrichment','targets']}
    seen=set()
    with (pysam.TabixFile(bed) if contig is not None else gzip.open(bed,'rt')) as handle:
        lines = (handle.fetch(contig) if contig in handle.contigs else []) if contig is not None else handle
        rows=(line.split() for line in lines if line.strip() and not line.startswith('#'))
        for (chrom,pos),group in itertools.groupby(rows,key=lambda f:(f[0],int(f[1]))):
            records={}
            for f in group:
                if len(f)<18: raise ValueError('Expected extended 18-column modkit bedMethyl')
                if f[3] not in ['m','h']:
                    if int(f[11]): raise ValueError('Unsupported CpG modification code: '+f[3])
                    continue
                if f[3] in records: raise ValueError('Duplicate modification at a CpG; expected combined strands')
                records[f[3]]=f
            if not records: continue
            seen.update(records)
            f=next(iter(records.values())); valid=int(f[9]); canonical=int(f[12])
            # N_other_mod preserves the other modification count even if its row is absent.
            combined=valid-canonical
            if not 0 <= combined <= valid: raise ValueError('Invalid bedMethyl counts')
            for record in records.values():
                if int(record[9])!=valid or int(record[12])!=canonical: raise ValueError('Inconsistent modification denominators')
            if not valid: continue
            values={'combined':combined,**{'5mC' if code=='m' else '5hmC':int(row[11]) for code,row in records.items()}}
            for scope in scopes(chrom,pos):
                for mod,number in values.items():
                    if not 0 <= number <= valid: raise ValueError('Invalid modified-base count')
                    d=metrics[scope][mod]; beta=number/valid; bucket=min(99,int(beta*100))
                    d['sites']+=1; d['depth_hist'][valid]+=1; d['modified']+=number; d['valid']+=valid
                    d['beta_sum']+=beta; d['beta_hist'][bucket]+=1
                    if valid>=10: d['beta_hist_depth10'][bucket]+=1
    for scope,mods in metrics.items():
        for mod,d in mods.items():
            d['available']=mod=='combined' or ('m' if mod=='5mC' else 'h') in seen
            d['reference_cpgs']=denominators[scope]
            d['callable_fraction']=d['sites']/denominators[scope] if denominators[scope] else None
            beta_sum=d.pop('beta_sum')
            d['mean_beta']=beta_sum/d['sites'] if d['sites'] else None
            d['weighted_beta']=d['modified']/d['valid'] if d['valid'] else None
            d['sites_at_depth']={str(t):sum(n for k,n in d['depth_hist'].items() if k>=t) for t in [1,5,10,20]}
    return metrics


def methylation_worker(job):
    return methylation_qc(*job)


def parallel_methylation(bed, fasta, enrichment, targets, threads):
    with pysam.FastaFile(fasta) as ref: contigs=list(ref.references)
    combined=None
    jobs=[(bed,fasta,enrichment,targets,c) for c in contigs]
    with ProcessPoolExecutor(max_workers=max(1,threads), mp_context=multiprocessing.get_context('spawn')) as pool:
        for result in pool.map(methylation_worker,jobs):
            if combined is None:
                combined=result
                for mods in combined.values():
                    for d in mods.values(): d['_beta_sum']=(d['mean_beta'] or 0)*d['sites']
                continue
            for scope,mods in result.items():
                for mod,d in mods.items():
                    dest=combined[scope][mod]
                    dest['_beta_sum']+=(d['mean_beta'] or 0)*d['sites']
                    for key in ['sites','modified','valid','reference_cpgs']: dest[key]+=d[key]
                    for key in ['depth_hist','beta_hist','beta_hist_depth10']: dest[key].update(d[key])
                    dest['available']=dest['available'] or d['available']
    for mods in combined.values():
        for d in mods.values():
            beta_sum=d.pop('_beta_sum')
            d['mean_beta']=beta_sum/d['sites'] if d['sites'] else None
            d['weighted_beta']=d['modified']/d['valid'] if d['valid'] else None
            d['callable_fraction']=d['sites']/d['reference_cpgs'] if d['reference_cpgs'] else None
            d['sites_at_depth']={str(t):sum(n for k,n in d['depth_hist'].items() if k>=t) for t in [1,5,10,20]}
    return combined


def plot(hist,title):
    pairs=sorted((float(k),v) for k,v in hist.items())
    if not pairs: return '<p>No observations</p>'
    low=0.; high=max(1.,pairs[-1][0]+1)
    n=min(100,max(1,int(high-low))); step=(high-low)/n
    values=[0]*n
    for key,count in pairs: values[min(n-1,int((key-low)/step))]+=count
    top=max(values) or 1; width=600/n
    bars=''.join(f'<rect x="{i*width:.2f}" y="{150-v/top*140:.2f}" width="{max(.5,width-1):.2f}" height="{v/top*140:.2f}"><title>{low+i*step:g}–{low+(i+1)*step:g}: {v}</title></rect>' for i,v in enumerate(values))
    return f'<h3>{html.escape(title)}</h3><svg viewBox="0 0 620 175" role="img" aria-label="{html.escape(title)}" style="max-width:650px;fill:#287a9c">{bars}<text x="0" y="170">{low:g}</text><text x="550" y="170">{high:g}</text></svg>'


def render_report(data):
    bam=data['alignment']; meth=data['methylation']; esc=lambda v:html.escape(str(v))
    sections=[f'<h1>{esc(data["sample"])} QC</h1>', '<p>Primary alignments; coverage includes duplicate/QC-failed flags and excludes deletions, skips, secondary and supplementary alignments. Lengths are sequenced query lengths. CpG beta uses valid modification calls.</p>']
    sections.append('<h2>Input yield</h2><pre>'+esc(json.dumps(data.get('input_yield', {}),indent=2))+'</pre>')
    sections.append('<h2>Yield and alignment</h2><pre>'+esc(json.dumps({**bam['counts'],'alignment_rate':bam['alignment_rate'],'on_enrichment_fraction_mapped':bam['on_enrichment_fraction_mapped'],'on_enrichment_fraction_all':bam['on_enrichment_fraction_all']},indent=2))+'</pre>')
    sections.append('<h2>Read lengths</h2><table><tr><th>Group</th><th>Reads</th><th>Bases</th><th>Mean</th><th>Median</th><th>N50</th></tr>')
    for k,d in bam['read_lengths'].items(): sections.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [k,d['reads'],d['bases'],d['mean'],d['median'],d['n50']])+'</tr>')
    sections.append('</table>')
    for k,d in bam['read_lengths'].items(): sections.append(plot(d['histogram'],f'{k}: length (bp) / read count'))
    sections.append(plot(bam['mapq'],'Mapping quality / primary read count'))
    sections.append('<h2>Coverage</h2><table><tr><th>MAPQ ≥</th><th>Scope</th><th>Mean depth</th><th>Breadth 1× / 5× / 10× / 20×</th></tr>')
    for q,scopes in bam['coverage'].items():
        for scope,d in scopes.items():
            if not isinstance(d,dict): continue
            sections.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [q,scope,d['mean'],list(d['breadth'].values())])+'</tr>')
    sections.append('</table>')
    for q,scopes in bam['coverage'].items():
        for scope,d in scopes.items():
            if isinstance(d,dict): sections.append(plot(d['histogram'],f'{scope}: depth / bases at MAPQ ≥{q}'))
    for scope,mods in meth.items():
        sections.append(f'<h2>CpG methylation: {esc(scope)}</h2>')
        for mod,d in mods.items():
            if not d['available']: sections.append(f'<p>{mod}: unavailable</p>'); continue
            sections.append('<pre>'+esc(json.dumps({k:v for k,v in d.items() if 'hist' not in k},indent=2))+'</pre>')
            sections.extend([plot(d['beta_hist'],mod+' beta (0–99 percent bins) / sites'),plot(d['beta_hist_depth10'],mod+' beta at depth ≥10'),plot(d['depth_hist'],mod+' valid depth / sites')])
    sections.append('<h2>Warnings</h2><pre>'+esc('\n'.join(data.get('warnings', [])) or 'None')+'</pre>')
    sections.append('<h2>Input/preprocessing: '+esc(data.get('input_run',data['sample']))+'</h2><pre>'+esc(json.dumps(data['preprocessing'],indent=2))+'</pre>')
    sections.append('<p>Observed enrichment is not a measurement of adaptive-sampling acceptance/rejection decisions. Undefined metrics are null; no clinical pass/fail thresholds are applied.</p>')
    return '<!doctype html><meta charset="utf-8"><title>Sample QC</title><style>body{font-family:system-ui;margin:2em}td,th{padding:.4em;border:1px solid #ddd}table{border-collapse:collapse}pre{white-space:pre-wrap}</style>'+''.join(sections)


def main():
    p=argparse.ArgumentParser()
    for key in ['bam','fasta','enrichment','targets','bedmethyl','sample']: p.add_argument('--'+key,required=True)
    p.add_argument('--input-run'); p.add_argument('--input-scope', choices=['run','sample'], default='sample'); p.add_argument('--threads',type=int,default=8); p.add_argument('--preprocessing',nargs='*',default=[])
    a=p.parse_args()
    if a.threads < 1: p.error('--threads must be at least 1')
    Path('qc').mkdir(exist_ok=True)
    data=dict(schema_version=1,sample=a.sample,alignment=bam_qc(a.bam,a.fasta,a.enrichment,a.targets,a.threads),
              methylation=parallel_methylation(a.bedmethyl,a.fasta,a.enrichment,a.targets,a.threads),
              preprocessing={Path(f).name:json.loads(Path(f).read_text()) for f in a.preprocessing})
    data['warnings'] = []
    if not data['alignment']['counts'].get('mapped_primary'): data['warnings'].append('No mapped primary reads')
    for scope in ['enrichment','targets','off_enrichment']:
        if not data['alignment']['coverage']['0'][scope]['aligned_bases']: data['warnings'].append('No aligned-base coverage in '+scope)
    if not data['methylation']['genome']['combined']['sites']: data['warnings'].append('No callable primary-genome CpGs')
    data['input_run'] = a.input_run or a.sample
    data['preprocessing']['input_scope'] = a.input_scope
    raw=data['preprocessing'].get('input_qc.json', {})
    data['input_yield']={'run':data['input_run'],'scope':data['preprocessing']['input_scope'],
                         'reads':raw.get('reads'),'bases':raw.get('bases'),
                         'modified_read_fraction':raw.get('modified_reads',0)/raw['reads'] if raw.get('reads') else None}
    trimmed=data['preprocessing'].get('trim_qc.json')
    if trimmed: data['input_yield']['post_trim']={k:trimmed.get(k) for k in ['reads','bases','modified_reads']}
    data['definitions']={'aggregate_coverage_and_cpg_contigs':'primary chromosomes 1–22/X/Y; other contigs reported separately','coverage_mapq':[0,20], 'read_overlap':'any aligned query base in merged enrichment intervals', 'coverage_flags':'primary, including duplicate and QC-failed flags','beta':'modified / valid calls', 'cpg_regions':'dyad forward-C coordinate'}
    Path('qc/metrics.json').write_text(json.dumps(data,indent=2,allow_nan=False))
    Path('qc/index.html').write_text(render_report(data))
    with open('qc/targets.tsv','w') as out:
        w=csv.writer(out,delimiter='\t'); w.writerow(['mapq','target','chrom','start','end','mean_depth','breadth_1','breadth_5','breadth_10','breadth_20'])
        for contig in data['alignment']['contigs']:
            for q,rows in contig['targets'].items():
                for label,d in rows.items(): w.writerow([q,label,d['chrom'],d['start'],d['end'],d['mean'],*[d['breadth'][str(t)] for t in [1,5,10,20]]])
    with open('qc/summary.tsv','w') as out:
        w=csv.writer(out,delimiter='\t'); w.writerow(['metric','value'])
        def walk(obj,prefix=''):
            for key,value in obj.items():
                path=f'{prefix}.{key}' if prefix else str(key)
                if isinstance(value,dict) and 'hist' not in str(key): yield from walk(value,path)
                elif not isinstance(value,(list,dict)): yield path,value
        w.writerows(walk({k:v for k,v in data.items() if k!='definitions'}))

if __name__=='__main__': main()
