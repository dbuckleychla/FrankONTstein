#!/usr/bin/env python3
"""Validate ONT methylation BAMs without dropping records or modification tags."""
import argparse
import json
import pysam


def check(path, unaligned=False):
    reads = modified = 0
    groups = set()
    with pysam.AlignmentFile(path, 'rb', check_sq=False) as bam:
        header_groups = {rg['ID'] for rg in bam.header.to_dict().get('RG', [])}
        for read in bam.fetch(until_eof=True):
            reads += 1
            if unaligned and not read.is_unmapped:
                raise ValueError(f'{path}: expected unaligned BAM')
            if read.has_tag('RG'):
                groups.add(read.get_tag('RG'))
            mm, ml = read.has_tag('MM'), read.has_tag('ML')
            if mm != ml:
                raise ValueError(f'{read.query_name}: MM and ML must occur together')
            if mm:
                if read.has_tag('MN') and read.get_tag('MN') != read.query_length:
                    raise ValueError(f'{read.query_name}: stale MN tag after sequence change')
                decoded = read.modified_bases
                if decoded is None:
                    raise ValueError(f'{read.query_name}: invalid modification encoding')
                if sum(len(v) for v in decoded.values()) != len(read.get_tag('ML')):
                    raise ValueError(f'{read.query_name}: MM/ML length mismatch')
                modified += 1
    if not reads or not modified:
        raise ValueError(f'{path}: no reads with methylation tags; Classy requires modified-base calls')
    if groups - header_groups:
        raise ValueError(f'{path}: read groups missing from header: {groups - header_groups}')
    return {'reads': reads, 'modified_reads': modified, 'read_groups': sorted(groups)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('bam')
    parser.add_argument('--unaligned', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.bam, args.unaligned), indent=2))
