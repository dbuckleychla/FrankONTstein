#!/usr/bin/env python3
"""Build a compatible header for lossless concatenation without scanning reads."""
import argparse
import json
from pathlib import Path
import pysam


def combined_header(paths):
    headers = []
    result = {}
    groups = {'RG': {}, 'PG': {}}
    comments = []
    varied_commands = set()
    for path in paths:
        with pysam.AlignmentFile(str(path), 'rb', check_sq=False) as bam:
            header = bam.header.to_dict()
        headers.append({'input': str(path), 'header': header})
        if len(headers) == 1:
            result = {k: v for k, v in header.items() if k not in ('RG', 'PG', 'CO')}
        elif header.get('SQ', []) != result.get('SQ', []):
            raise ValueError('samtools cat requires identical sequence dictionaries in all input BAMs')
        for kind in ('RG', 'PG'):
            for entry in header.get(kind, []):
                identity = entry['ID']
                previous = groups[kind].get(identity)
                if previous is None:
                    groups[kind][identity] = dict(entry)
                elif kind == 'PG' and {k:v for k,v in previous.items() if k != 'CL'} == {k:v for k,v in entry.items() if k != 'CL'}:
                    # Shard-specific command paths differ. Keep the shared program
                    # identity; preserve exact per-input commands in provenance.
                    if previous.get('CL') != entry.get('CL'):
                        previous.pop('CL', None)
                        varied_commands.add(identity)
                elif previous != entry:
                    raise ValueError(f'Conflicting @{kind} ID {identity!r}; cannot concatenate without changing read metadata')
        for comment in header.get('CO', []):
            if comment not in comments:
                comments.append(comment)
    if not headers:
        raise ValueError('No input BAMs')
    result.setdefault('HD', {})['SO'] = 'unsorted'
    result['HD'].pop('SS', None)
    for kind, entries in groups.items():
        if entries:
            result[kind] = list(entries.values())
    if varied_commands:
        comments.append('Shard-specific PG command lines are recorded in cat_header.json; shared PG entries omit ambiguous CL fields.')
    if comments:
        result['CO'] = comments
    return str(pysam.AlignmentHeader.from_dict(result)), {'inputs': headers, 'programs_with_multiple_commands': sorted(varied_commands)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provenance', required=True)
    parser.add_argument('bams', nargs='+')
    args = parser.parse_args()
    header, provenance = combined_header(args.bams)
    Path(args.provenance).write_text(json.dumps(provenance, indent=2) + '\n')
    print(header, end='')
