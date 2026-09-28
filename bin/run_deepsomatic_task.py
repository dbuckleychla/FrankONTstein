#!/usr/bin/env python3
"""Run one offline, tumor-only DeepSomatic task with auditable arguments."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

MODEL_TYPE = 'ONT_TUMOR_ONLY'
RELEASE = '1.10.0'
ASSET_ROOT = Path('/opt/models/deepsomatic')
PON_NAME = 'PON_dbsnp138_gnomad_PB1000g_pon.vcf.gz'


def build_command(executable, bam, ref, targets, sample, cpus, output='results', intermediate='intermediate_results', dry_run=False):
    if cpus < 1:
        raise ValueError('DeepSomatic requires at least one CPU/shard')
    return [str(executable), '--model_type=' + MODEL_TYPE,
            '--ref=' + str(Path(ref).resolve()), '--reads_tumor=' + str(Path(bam).resolve()),
            '--regions=' + str(Path(targets).resolve()), '--output_vcf=' + str(Path(output).resolve() / 'somatic.vcf.gz'),
            '--sample_name_tumor=' + sample, '--num_shards=' + str(cpus),
            '--logging_dir=' + str(Path(output).resolve() / 'logs'),
            '--intermediate_results_dir=' + str(Path(intermediate).resolve()),
            '--use_default_pon_filtering=true', '--dry_run=' + str(dry_run).lower()]


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def bundled_assets(root=ASSET_ROOT):
    """Check the release's offline ONT model and default ONT panel."""
    root = Path(root)
    required = [root / 'ont_tumor_only' / name for name in (
        'saved_model.pb', 'model.example_info.json',
        'variables/variables.index', 'variables/variables.data-00000-of-00001')]
    required += [root / 'pons' / PON_NAME, root / 'pons' / (PON_NAME + '.tbi')]
    checksums = {}
    for path in required:
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Pinned DeepSomatic image is missing bundled asset: ' + str(path))
        checksums[str(path)] = sha256(path)
    return checksums


def find_executable():
    found = shutil.which('run_deepsomatic')
    if found:
        return found
    path = Path('/opt/deepvariant/bin/deepsomatic/run_deepsomatic')
    if path.is_file() and os.access(path, os.X_OK):
        return str(path)
    raise ValueError('Pinned image does not contain run_deepsomatic')


def gpu_environment(gpu):
    env = dict(os.environ)
    if not gpu:
        env['CUDA_VISIBLE_DEVICES'] = '-1'
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('bam', 'ref', 'targets', 'sample', 'image'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--cpus', type=int, required=True)
    parser.add_argument('--gpu', action='store_true')
    args = parser.parse_args()
    executable = find_executable()
    output = Path('results')
    (output / 'logs').mkdir(parents=True, exist_ok=True)
    env = gpu_environment(args.gpu)
    if args.gpu:
        subprocess.run([sys.executable, '-c',
                        "import tensorflow as tf; assert tf.config.list_physical_devices('GPU'), 'DeepSomatic cannot access its assigned GPU'"],
                       env=env, check=True)
    assets = bundled_assets()
    version = subprocess.run([executable, '--version'], env=env, check=True,
                             text=True, capture_output=True)
    (output / 'logs/version.log').write_text(version.stdout + version.stderr)
    if 'DeepVariant version ' + RELEASE not in version.stdout:
        raise ValueError('DeepSomatic runtime version does not match pinned release ' + RELEASE)
    command = build_command(executable, args.bam, args.ref, args.targets, args.sample, args.cpus)
    provenance = dict(release=RELEASE, image=args.image, model_type=MODEL_TYPE,
                      bundled_assets_sha256=assets, runtime_version=version.stdout.strip(),
                      default_pon_filtering=True, regions='targets_bed',
                      targets_sha256=sha256(args.targets), sample=args.sample,
                      cpus=args.cpus, num_shards=args.cpus, gpu=args.gpu, command=command)
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    Path('versions.yml').write_text('DeepSomatic: ' + RELEASE + '\n')
    with (output / 'logs/runner.log').open('w') as log:
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end='', flush=True)
        status = process.wait()
    if status:
        raise SystemExit(status if status > 0 else 128 - status)
    for name in ('somatic.vcf.gz', 'somatic.vcf.gz.tbi'):
        if not (output / name).is_file() or not (output / name).stat().st_size:
            raise ValueError('DeepSomatic did not emit a nonempty ' + name)


if __name__ == '__main__':
    main()
