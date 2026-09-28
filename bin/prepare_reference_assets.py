#!/usr/bin/env python3
"""Make NASVAR repeat exclusions and duplicate target labels explicit and auditable."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
from check_reference import contigs,contig_aliases


def prepare(fai, assets):
    assets=Path(assets);lengths=contigs(fai)
    aliases=contig_aliases(assets/'reference.json',lengths)
    excluded=Counter();mapped=Counter();kept=0
    src=assets/'repeats.bed';temp=assets/'repeats.prepared.bed'
    with src.open() as inp,temp.open('w') as out,(assets/'repeats.excluded.bed').open('w') as omitted:
        for line in inp:
            if not line.strip() or line.startswith(('#','track ','browser ')):
                out.write(line);continue
            fields=line.split();chrom=fields[0] if fields[0] in lengths else aliases.get(fields[0])
            if chrom is None:
                excluded[fields[0]]+=1;omitted.write(line);continue
            if not 0<=int(fields[1])<int(fields[2])<=lengths[chrom]:
                raise ValueError('Repeat coordinates exceed validated reference: '+line.strip())
            if fields[0]!=chrom:mapped[fields[0]+'->'+chrom]+=1
            fields[0]=chrom;out.write('\t'.join(fields)+'\n');kept+=1
    if not kept:raise ValueError('No repeats match the reference')
    temp.replace(src)
    labels=defaultdict(set)
    for line in (assets/'targets.bed').read_text().splitlines():
        fields=line.split()
        if len(fields)>3 and not line.startswith(('#','track ','browser ')):labels[fields[3]].add(fields[0])
    duplicated={k:sorted(v) for k,v in labels.items() if len(v)>1}
    audit=dict(repeats_retained=kept,repeats_excluded=sum(excluded.values()),excluded_contigs=dict(excluded),
               renamed_contigs=dict(mapped),ambiguous_target_names=duplicated,
               target_policy='Targets remain unchanged; NASVAR may retain only one locus for repeated gene names.',
               note='No contigs or coordinates are guessed. Only explicit reference-config aliases are used.')
    (assets/'reference_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    return audit


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('fai');p.add_argument('assets');a=p.parse_args();prepare(a.fai,a.assets)
