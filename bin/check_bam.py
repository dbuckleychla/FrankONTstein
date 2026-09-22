#!/usr/bin/env python3
"""Validate ONT methylation BAMs without dropping records or modification tags."""
import argparse
import json
import multiprocessing
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import pysam


def validate_modifications(read):
    decoded = read.modified_bases
    if decoded is None:
        raise ValueError(f'{read.query_name}: invalid modification encoding')
    if sum(len(v) for v in decoded.values()) != len(read.get_tag('ML')):
        raise ValueError(f'{read.query_name}: MM/ML length mismatch')


def validate_batch(records):
    # Only sequence, orientation and modification tags affect MM/ML decoding.
    # Avoid serializing qualities, alignments and unrelated auxiliary tags.
    for name, sequence, flag, mm, ml in records:
        read = pysam.AlignedSegment()
        read.query_name = name
        read.query_sequence = sequence
        read.flag = flag
        read.set_tag('MM', mm)
        read.set_tag('ML', ml)
        validate_modifications(read)


def check(path, unaligned=False, threads=1):
    if threads < 1:
        raise ValueError('threads must be at least 1')
    reads = modified = 0
    groups = set()
    # One reader plus N-1 decoding workers; no index or temporary BAMs needed.
    # Spawn avoids inheriting HTSlib handles across a fork.
    pool = (ProcessPoolExecutor(max_workers=threads - 1,
                               mp_context=multiprocessing.get_context('spawn'))
            if threads > 1 else None)
    pending = deque()
    batch = []
    batch_bytes = 0
    try:
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
                    if pool is None:
                        validate_modifications(read)
                    else:
                        mm_tag, ml_tag = read.get_tag('MM'), read.get_tag('ML')
                        batch.append((read.query_name, read.query_sequence, read.flag, mm_tag, ml_tag))
                        batch_bytes += read.query_length + len(mm_tag) + len(ml_tag)
                        # Bound both memory and read count, including ultra-long reads.
                        if batch_bytes >= 2_000_000 or len(batch) >= 512:
                            pending.append(pool.submit(validate_batch, batch))
                            batch, batch_bytes = [], 0
                            if len(pending) >= 2 * (threads - 1):
                                pending.popleft().result()
                    modified += 1
        if batch:
            pending.append(pool.submit(validate_batch, batch))
        for future in pending:
            future.result()
    finally:
        if pool is not None:
            for future in pending:
                future.cancel()
            pool.shutdown(wait=True, cancel_futures=True)
    if not reads or not modified:
        raise ValueError(f'{path}: no reads with methylation tags; Classy requires modified-base calls')
    if groups - header_groups:
        raise ValueError(f'{path}: read groups missing from header: {groups - header_groups}')
    return {'reads': reads, 'modified_reads': modified, 'read_groups': sorted(groups)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('bam')
    parser.add_argument('--unaligned', action='store_true')
    parser.add_argument('--threads', type=int, default=1,
                        help='Total CPU budget: one BAM reader plus decoding workers (default: 1)')
    args = parser.parse_args()
    print(json.dumps(check(args.bam, args.unaligned, args.threads), indent=2))
