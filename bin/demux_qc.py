#!/usr/bin/env python3
"""Count assigned and unclassified demux yield, without decoding MM/ML again."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import pysam


def count(path):
    reads=bases=0
    with pysam.AlignmentFile(path,'rb',check_sq=False) as bam:
        for r in bam.fetch(until_eof=True):
            if r.is_secondary or r.is_supplementary: continue
            reads+=1; bases+=r.query_length or 0
    return Path(path).name,dict(reads=reads,bases=bases)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--threads',type=int,default=8);p.add_argument('--run',required=True);p.add_argument('bams',nargs='+');a=p.parse_args()
    with ProcessPoolExecutor(max_workers=max(1,min(a.threads,len(a.bams)))) as pool: results=dict(pool.map(count,a.bams))
    print(json.dumps(dict(run=a.run,barcodes=results),indent=2))
