#!/usr/bin/env python3
"""Execute pinned NASVAR safely, preserving standalone subcommand result sections.

The pinned CLI can log an error and exit zero. Treat ERROR diagnostics and missing
expected sections as task failures. Its standalone collectors overwrite JSON, so
merge sections explicitly between steps (not variant calls across callers).
"""
import argparse
import json
import re
import subprocess
from pathlib import Path


def execute(args, log):
    result = subprocess.run(['nasvar', '--log-level', 'info', *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    Path(log).write_text(result.stdout)
    if result.returncode or re.search(r'\bERROR\b', result.stdout):
        raise RuntimeError(f'NASVAR failed; inspect {log}')


def run(a):
    prefix = str(Path('nasvar') / a.sample)
    Path('nasvar').mkdir(exist_ok=True)
    target = Path(prefix + '.result.json')
    common = ['--out-prefix', prefix, '--reference', a.reference]
    bam = ['--bam', a.bam, '--ref-fasta', a.fasta]
    config = ['--config', a.config]
    merged = {}

    def step(name, args, sections=()):
        execute(args, f'nasvar/{name}.log')
        if sections:
            fresh = json.loads(target.read_text())
            for section in sections:
                if fresh.get(section) is None:
                    raise RuntimeError(f'NASVAR {name}: missing {section}')
            merged.update(fresh)
            target.write_text(json.dumps(merged, indent=2))

    if a.tier == 'tertiary':
        step('pipeline', ['pipeline', a.bam, a.repeats, a.enriched, a.sites,
                         a.targets, a.fasta, a.gff, prefix, *config,
                         '--reference', a.reference], ('cnv', 'karyotype', 'fusions', 'snv', 'itd'))
    else:
        step('coverage', ['coverage', *common, *bam, '--repeats', a.repeats])
        if not Path(prefix + '.coverage.tsv').is_file():
            raise RuntimeError('NASVAR coverage output missing')
        step('maf', ['maf', *common, *bam, '--enriched', a.enriched,
                     '--sites', a.sites, '--repeats', a.repeats])
        if not Path(prefix + '.maf').is_file():
            raise RuntimeError('NASVAR MAF output missing')
        step('karyotype', ['karyotype', *common, *config, '--coverage', prefix + '.coverage.tsv',
                          '--maf', prefix + '.maf', '--sites', a.sites,
                          '--enriched', a.enriched, '--repeats', a.repeats], ('karyotype',))
        ratio = merged['karyotype'].get('blast_ratio')
        ratio_args = ['--blast-ratio', str(ratio)] if ratio is not None else []
        step('cnv', ['cnv', *common, *bam, *config, '--targets', a.targets,
                     '--coverage', prefix + '.coverage.tsv', *ratio_args, '--force'], ('cnv',))
        step('fusions', ['fusions', *common, *bam, *config, '--targets', a.targets,
                         '--repeats', a.repeats, '--gff', a.gff, '--force'], ('fusions',))
        # Empty fusion results are valid; the CLI handles the no-consensus case.
        step('breakpoints', ['breakpoints', *common, *bam, '--force'])
        if target.exists():
            merged.update(json.loads(target.read_text()))
            target.write_text(json.dumps(merged, indent=2))
    step('report', ['report', '--out-prefix', prefix, *config, '--targets', a.targets])
    if not Path(prefix + '.report.html').is_file():
        raise RuntimeError('NASVAR report missing')
    execute(['--version'], 'nasvar/versions.txt')

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ['sample', 'bam', 'fasta', 'repeats', 'enriched', 'sites', 'targets', 'gff', 'config', 'reference']:
        p.add_argument('--' + name, required=True)
    p.add_argument('--tier', choices=['secondary', 'tertiary'], required=True)
    run(p.parse_args())
