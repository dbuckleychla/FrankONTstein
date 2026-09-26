#!/usr/bin/env python3
"""POD5 routing/resume contracts using stubs; requires no models or GPU."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--nextflow-jar')
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
command = ['java', '-jar', a.nextflow_jar] if a.nextflow_jar else ['nextflow']
with tempfile.TemporaryDirectory(prefix='frankontstein-basecall-') as scratch:
    scratch = Path(scratch)
    config = scratch / 'stub.config'
    config.write_text('profiles { local {} ; docker { docker.enabled = false } }\napptainer.enabled = false\n')
    for name in ['model', 'modified', 'r1041_e82_400bps_sup_v520_with_mv', 'raw', 'raw/nested']:
        (scratch / name).mkdir()
    for name in ['a', 'b', 'c']:
        (scratch / 'raw' / (name + '.pod5')).touch()
    (scratch / 'raw/nested/ignored.pod5').touch()
    params = scratch / 'params.json'
    params.write_text(json.dumps({'steps': {'clair3': {'model': str(scratch / 'r1041_e82_400bps_sup_v520_with_mv')}, 'basecall': {'model': str(scratch / 'model'), 'modified_models': [str(scratch / 'modified')]}}}))
    manifest = scratch / 'input.csv'
    manifest.write_text(f'sample,run,pod5\nrun1,run1,{scratch / "raw"}\n')
    subprocess.run(['python3', 'tests/make_contract_tools.py', str(scratch / 'tools')], cwd=root, check=True)
    env = dict(os.environ, NXF_SYNTAX_PARSER='v2', PATH=str(scratch / 'tools') + os.pathsep + os.environ['PATH'])
    base = command + ['run', '.', '-stub-run', '-profile', 'local,docker', '-c', str(config), '-ansi-log', 'false',
                      '--basecall', '--basecall_device', '0', '--max_cpus', '2', '--max_memory', '1 GB',
                      '--reference_bundle', 'tests/fixtures/bundle.json', '--targets_bed', 'tests/fixtures/regions.bed',
                      '--enrichment_bed', 'tests/fixtures/regions.bed', '--image_manifest', 'tests/fixtures/images.json',
                      '-params-file', str(params)]
    cases = [
        ('primary', ['--pod5', str(scratch / 'raw'), '--sample_id', 'sample1', '--basecall_tasks', '2', '--basecall_max_forks', '1'], ['sample1'], 2),
        ('secondary', ['--input', str(manifest), '--demux_samplesheet', 'tests/fixtures/demux.csv', '--trim'], ['sample1', 'sample2'], 3),
        ('tertiary', ['--pod5', str(scratch / 'raw/a.pod5'), '--sample_id', 'sample1', '--disable_qc', 'true'], ['sample1'], 1),
    ]
    for tier, extra, samples, batches in cases:
        out = scratch / tier
        args = base + ['--' + tier, '--outdir', str(out), '-work-dir', str(scratch / (tier + '-work'))] + extra
        subprocess.run(args, cwd=root, env=env, check=True)
        result = json.loads((out / 'manifest.json').read_text())
        records = [r for r in result['analyses'] if r['analysis'] == 'basecalling']
        assert sorted(r['sample'] for r in records) == samples, records
        assert all(r['status'] == 'completed' and all((out / f).exists() for f in r['files']) for r in records)
        for sample in samples:
            assert (out / sample / 'alignment' / f'{sample}.bam').exists()
            assert (out / sample / 'methylation' / f'{sample}.cpg.bedmethyl.gz').exists()
        with (out / 'pipeline_info/trace.tsv').open() as f:
            trace = list(csv.DictReader(f, delimiter='\t'))
        assert sum('DORADO_BASECALL (' in r['name'] for r in trace) == batches, trace
        assert sum('PREPARE_BAM (' in r['name'] for r in trace) == 1
        subprocess.run(args + ['-resume', result['run']['session_id']], cwd=root, env=env, check=True)
        with (out / 'pipeline_info/trace.tsv').open() as f:
            trace = list(csv.DictReader(f, delimiter='\t'))
        assert all(r['status'] == 'CACHED' for r in trace if 'RESULTS_INDEX' not in r['name']), trace
    # Independent sample groups and identical source basenames must not collide.
    (scratch / 'other').mkdir()
    (scratch / 'other/a.pod5').touch()
    multi = scratch / 'multi.csv'
    multi.write_text(f'sample,run,pod5\nsample1,r1,{scratch / "raw/a.pod5"}\n'
                     + f'sample1,r1,{scratch / "other/a.pod5"}\nsample2,r2,{scratch / "raw/b.pod5"}\n')
    out = scratch / 'multiple-samples'
    subprocess.run(base + ['--input', str(multi), '--outdir', str(out), '-work-dir', str(scratch / 'multi-work')],
                   cwd=root, env=env, check=True)
    records = json.loads((out / 'manifest.json').read_text())['analyses']
    assert sorted(r['sample'] for r in records if r['analysis'] == 'basecalling') == ['sample1', 'sample2']
    with (out / 'pipeline_info/trace.tsv').open() as f:
        trace = list(csv.DictReader(f, delimiter='\t'))
    assert sum('PREPARE_BAM (' in r['name'] for r in trace) == 2
    assert sum('DORADO_BASECALL (' in r['name'] for r in trace) == 3
    # Process failures must be attributed to every sample mapped to the raw run.
    for process in ['DORADO_BASECALL', 'CHECK_BASECALL_MODELS']:
        config.write_text("profiles { local {} ; docker { docker.enabled = false } }\n"
                          + "process { withName: " + process + " { beforeScript = 'exit 23' } }\n")
        out = scratch / ('failed-' + process)
        failed = subprocess.run(base + ['--input', str(manifest), '--demux_samplesheet', 'tests/fixtures/demux.csv',
                                        '--outdir', str(out), '-work-dir', str(scratch / ('work-' + process))],
                                cwd=root, env=env, capture_output=True, text=True)
        assert failed.returncode != 0
        failure_records = json.loads((out / 'manifest.json').read_text())['analyses']
        statuses = {r['sample']: r['status'] for r in failure_records if r['analysis'] == 'basecalling'}
        assert statuses == {'sample1': 'failed', 'sample2': 'failed'}, (statuses, failed.stdout, failed.stderr)
    config.write_text('profiles { local {} ; docker { docker.enabled = false } }\n')
    # Duplicate files reached through overlapping directory/file entries fail before basecalling.
    manifest.write_text(f'sample,run,pod5\ns,s,{scratch / "raw"}\ns,s,{scratch / "raw/a.pod5"}\n')
    failure = subprocess.run(base + ['--input', str(manifest), '--outdir', str(scratch / 'duplicate')], cwd=root, env=env, text=True, capture_output=True)
    assert failure.returncode != 0 and 'Duplicate resolved POD5' in failure.stdout + failure.stderr
print('POD5 singleton/multiplexed tier routing and resume contracts passed (stubs only)')
