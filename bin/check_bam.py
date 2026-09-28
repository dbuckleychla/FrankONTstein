#!/usr/bin/env python3
"""Bounded BAM input sanity check; never decode or validate modification arrays."""
import argparse
import json
import pysam


def check(path, unaligned=False, threads=1, require_cpg_modifications=False, require_moves=False, max_reads=1000):
    if threads < 1 or max_reads < 1:
        raise ValueError('threads and max_reads must be positive')
    pysam.quickcheck('-u', str(path))
    reads = bases = modified = 0
    groups = set()
    truncated = False
    with pysam.AlignmentFile(path, 'rb', check_sq=False) as bam:
        header_groups = {rg['ID'] for rg in bam.header.to_dict().get('RG', [])}
        for read in bam.fetch(until_eof=True):
            if reads >= max_reads:
                truncated = True
                break
            reads += 1
            bases += read.query_length or 0
            if unaligned and not read.is_unmapped:
                raise ValueError(f'{path}: expected unaligned BAM')
            if read.has_tag('RG'):
                groups.add(read.get_tag('RG'))
            if require_moves and not read.is_secondary and not read.is_supplementary and not read.has_tag('mv'):
                raise ValueError('Missing mv tag required by selected Clair3 model in sampled reads')
            modified += int(read.has_tag('MM') and read.has_tag('ML'))
    if not reads or not modified:
        raise ValueError(f'{path}: no reads with methylation tags in bounded input sample')
    if groups - header_groups:
        raise ValueError(f'{path}: sampled read groups missing from header')
    # Sample totals must never be presented as full input yield.
    return dict(validation='bounded_presence_only', exhaustive=False, sampled_reads=reads,
                sampled_bases=bases, sampled_modified_reads=modified,
                sample_limit=max_reads, reached_eof=not truncated,
                reads=None if truncated else reads, bases=None if truncated else bases,
                modified_reads=None if truncated else modified, read_groups=sorted(groups),
                modification_encoding_checked=False)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bam'); p.add_argument('--unaligned',action='store_true')
    p.add_argument('--threads',type=int,default=1,help='Compatibility option; bounded check is single-threaded')
    p.add_argument('--max-reads',type=int,default=1000)
    p.add_argument('--require-cpg-modifications',action='store_true',help='Compatibility option; modification encoding is trusted')
    p.add_argument('--require-moves',action='store_true')
    a=p.parse_args()
    print(json.dumps(check(a.bam,a.unaligned,a.threads,a.require_cpg_modifications,a.require_moves,a.max_reads),indent=2))
