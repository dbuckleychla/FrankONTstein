#!/usr/bin/env python3
"""Publish indexed sample-normalized variants and separate explicit-PASS records."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import pysam


def finalize(source, fai, sample, prefix, caller):
    lengths = {x[0]: int(x[1]) for line in Path(fai).read_text().splitlines() if (x := line.split('\t'))}
    output = Path('variants')
    output.mkdir(exist_ok=True)
    normalized = output / (prefix + '.normalized.vcf')
    passed = output / (prefix + '.pass.vcf')
    filters = Counter()
    with pysam.VariantFile(str(source)) as vcf:
        original_samples = list(vcf.header.samples)
        if len(original_samples) > 1:
            if sample not in original_samples:
                raise ValueError('Multi-sample VCF lacks expected sample; fix BAM read-group sample metadata before calling')
            vcf.subset_samples([sample])
        header = str(vcf.header).splitlines()
        # QDNAseq uses bare chromosomes and may omit contig declarations.
        if caller == 'qdnaseq':
            header = [line for line in header if not line.startswith('##contig=')]
        declared = {m[1] for line in header if (m := re.match(r'##contig=<ID=([^,>]+)', line))}
        additional = [f'##contig=<ID={name},length={size}>' for name,size in lengths.items() if name not in declared]
        columns = header.pop().split('\t')
        if original_samples:
            columns = columns[:9] + [sample]
        header += additional + ['##FrankONTstein_sample=' + sample, '\t'.join(columns)]
        header_text = '\n'.join(header) + '\n'
        with normalized.open('w') as all_out, passed.open('w') as pass_out:
            all_out.write(header_text)
            pass_out.write(header_text)
            for record in vcf:
                fields = str(record).rstrip('\n').split('\t')
                if caller == 'qdnaseq' and fields[0] not in lengths:
                    renamed = 'chrM' if fields[0] in ('MT','M') else 'chr' + fields[0]
                    if renamed not in lengths:
                        raise ValueError('QDNAseq contig cannot be resolved against reference: ' + fields[0])
                    fields[0] = renamed
                if fields[0] not in lengths:
                    raise ValueError('Variant contig absent from validated reference: ' + fields[0])
                # PASS must be the exact FILTER value; '.' is unassessed, not PASS.
                filters[fields[6]] += 1
                line = '\t'.join(fields) + '\n'
                all_out.write(line)
                if fields[6] == 'PASS':
                    pass_out.write(line)
    assessed = any(key != '.' for key in filters)
    # For an empty VCF, retain an empty PASS deliverable when the source declares filters.
    assessed = assessed or (not filters and any(line.startswith('##FILTER=') for line in header))
    for path in (normalized, passed) if assessed else (normalized,):
        pysam.tabix_compress(str(path), str(path) + '.gz', force=True)
        pysam.tabix_index(str(path) + '.gz', preset='vcf', force=True)
        path.unlink()
    if not assessed:
        passed.unlink()
    status = dict(sample=sample, caller=caller, input=str(source), original_samples=original_samples,
                  total_records=sum(filters.values()), filter_counts=dict(filters),
                  pass_records=filters.get('PASS',0),
                  pass_filter_status='applied' if assessed else 'not_applicable_all_records_unassessed',
                  policy='Only exact FILTER=PASS; unassessed dot records are never promoted to PASS',
                  contig_normalization='reference-matched chr names' if caller=='qdnaseq' else 'unchanged')
    (output / (prefix + '.filtering.json')).write_text(json.dumps(status, indent=2) + '\n')
    return status


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('input','fai','sample','prefix','caller'): p.add_argument('--'+key, required=True)
    a=p.parse_args()
    finalize(a.input,a.fai,a.sample,a.prefix,a.caller)
