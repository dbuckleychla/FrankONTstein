#!/usr/bin/env python3
"""Check staged BED/GFF/site coordinates against the exact reference index."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PRIMARY_CONTIGS = [f'chr{i}' for i in range(1, 23)] + ['chrX', 'chrY']


def primary_contigs(lengths):
    missing = [name for name in PRIMARY_CONTIGS if name not in lengths]
    if missing:
        raise ValueError('FASTA index missing required primary contigs: ' + ', '.join(missing))


def contigs(fai):
    result = {}
    for line in Path(fai).read_text().splitlines():
        fields = line.split('\t')
        if len(fields) < 5 or fields[0] in result or int(fields[1]) <= 0:
            raise ValueError('Invalid or duplicate FAI entry')
        result[fields[0]] = int(fields[1])
    if not result:
        raise ValueError('Empty reference index')
    return result


def fasta_index(fasta, fai):
    """Validate FAI offsets/line widths against an uncompressed FASTA."""
    expected = {}
    for line in Path(fai).read_text().splitlines():
        fields = line.split('\t')
        expected[fields[0]] = tuple(map(int, fields[1:5]))
    actual = {}
    with open(fasta, 'rb') as stream:
        name = None
        length = offset = bases = width = 0
        short_line = False
        while True:
            line = stream.readline()
            if not line:
                if name is not None: actual[name] = (length, offset, bases, width)
                break
            if line.startswith(b'>'):
                if name is not None: actual[name] = (length, offset, bases, width)
                name = line[1:].split()[0].decode()
                if name in actual: raise ValueError('Duplicate FASTA contig')
                length, offset, bases, width, short_line = 0, stream.tell(), 0, 0, False
            else:
                seq = line.rstrip(b'\r\n')
                if name is None or not seq or short_line: raise ValueError('Invalid FASTA line wrapping')
                if not bases: bases, width = len(seq), len(line)
                elif len(seq) != bases or len(line) != width: short_line = True
                length += len(seq)
    if actual != expected: raise ValueError('FASTA content and FAI disagree')


def contig_aliases(config, lengths):
    """Use only aliases explicitly declared by the selected NASVAR reference."""
    aliases = {}
    for contig in json.loads(Path(config).read_text()).get('contigs', []):
        names = [contig.get('name'), contig.get('accession')]
        names = [name for name in names if name]
        present = [name for name in names if name in lengths]
        if not present:
            continue
        if len({lengths[name] for name in present}) != 1:
            raise ValueError(f'{config}: conflicting FASTA lengths for aliases {names}')
        for name in names:
            if name in aliases and aliases[name] != present[0]:
                raise ValueError(f'{config}: ambiguous contig alias {name}')
            aliases[name] = present[0]
    return aliases


def coordinates(path, lengths, kind='bed', aliases=None):
    count = 0
    skipped = Counter()
    mapped = Counter()
    aliases = aliases or {}
    with open(path) as handle:
        for number, line in enumerate(handle, 1):
            if kind == 'gff' and line.strip() == '##FASTA':
                break
            if not line.strip() or line.startswith(('#', 'track ', 'browser ')):
                continue
            f = line.rstrip('\r\n').split('\t') if kind == 'gff' else line.split()
            if kind == 'gff' and len(f) != 9:
                raise ValueError(f'{path}:{number}: GFF3 requires 9 tab-separated columns; got {len(f)}')
            try:
                if kind == 'gff':
                    start, end = int(f[3]) - 1, int(f[4])
                elif kind == 'sites':
                    start, end = int(f[1]) - 1, int(f[1])
                else:
                    start, end = int(f[1]), int(f[2])
            except (ValueError, IndexError) as exc:
                raise ValueError(f'{path}:{number}: invalid {kind} coordinate columns: {f[:5]!r}') from exc
            if not 0 <= start < end:
                raise ValueError(f'{path}:{number}: coordinate/contig incompatible with FASTA')
            chrom = f[0] if f[0] in lengths else aliases.get(f[0], f[0])
            if chrom not in lengths:
                skipped[f[0]] += 1
                continue
            if end > lengths[chrom]:
                raise ValueError(f'{path}:{number}: interval {f[0]}:{start}-{end} exceeds '
                                 f'FASTA contig {chrom} length {lengths[chrom]}')
            if chrom != f[0]: mapped[(f[0], chrom)] += 1
            count += 1
    if mapped:
        print(f'{path}: validated {sum(mapped.values())} records using reference-config contig aliases; '
              'file unchanged', file=sys.stderr)
    if skipped:
        names = ', '.join(sorted(skipped)[:10])
        if len(skipped) > 10: names += ', ...'
        print(f'{path}: skipped coordinate validation for {sum(skipped.values())} records '
              f'on {len(skipped)} contigs absent from FASTA ({names}); file unchanged', file=sys.stderr)
    if count == 0:
        raise ValueError(f'{path}: no coordinate records overlap FASTA contigs')

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('fai')
    p.add_argument('--fasta')
    p.add_argument('--bed', action='append', default=[])
    p.add_argument('--gff')
    p.add_argument('--sites')
    p.add_argument('--reference-config', help='NASVAR reference JSON containing contig aliases')
    args = p.parse_args()
    lengths = contigs(args.fai)
    primary_contigs(lengths)
    aliases = contig_aliases(args.reference_config, lengths) if args.reference_config else {}
    if args.fasta: fasta_index(args.fasta, args.fai)
    for bed in args.bed:
        coordinates(bed, lengths)
    for kind in ['gff', 'sites']:
        if getattr(args, kind):
            coordinates(getattr(args, kind), lengths, kind, aliases=aliases)
    print('Reference coordinates validated')
