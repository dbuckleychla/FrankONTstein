#!/usr/bin/env python3
"""Focused streaming length audit for existing indexed BAMs; no coverage rerun."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import pysam
from adaptive_qc import Regions, merged, read_bed, read_length_groups, lengths_summary


def collect(bam, enrichment, targets):
    groups=defaultdict(Counter)
    with pysam.AlignmentFile(str(bam),'rb') as handle:
        sizes=dict(zip(handle.references,handle.lengths))
        er=read_bed(enrichment,sizes); tr=read_bed(targets,sizes)
        regions={c:(Regions(merged(er.get(c,[]))),Regions(merged(tr.get(c,[])))) for c in sizes}
        empty=Regions([])
        for read in handle.fetch(until_eof=True):
            e,t=regions.get(read.reference_name,(empty,empty))
            for k in read_length_groups(read,e,t):
                groups[k][read.query_length or read.infer_query_length() or 0]+=1
    return {k:lengths_summary(groups[k]) for k in ['all','mapped','unmapped','on_target','off_target','on_enrichment','off_enrichment']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['bam','enrichment','targets','output']:p.add_argument('--'+name,required=True)
    a=p.parse_args()
    result={'read_lengths':collect(a.bam,a.enrichment,a.targets),'assets':{k:{'path':getattr(a,k),'sha256':hashlib.sha256(Path(getattr(a,k)).read_bytes()).hexdigest()} for k in ['enrichment','targets']}}
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
