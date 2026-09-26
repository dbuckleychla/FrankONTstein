#!/usr/bin/env python3
"""Validate offline Dorado model assets and capture their content provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def model_digest(path):
    path = Path(path)
    if not path.is_dir() or not (path / 'config.toml').is_file():
        raise ValueError(f'{path}: expected a Dorado model directory containing config.toml')
    files = sorted(p for p in path.rglob('*') if p.is_file())
    if not any(p.suffix == '.tensor' for p in files):
        raise ValueError(f'{path}: missing model tensor weights')
    digest = hashlib.sha256()
    for item in files:
        digest.update(item.relative_to(path).as_posix().encode() + b'\0')
        with item.open('rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
        digest.update(b'\0')
    return {'name': path.name, 'sha256': digest.hexdigest()}


def validate(model, modified, clair3=None, clair3_model=None):
    model, modified = Path(model), Path(modified)
    match = re.fullmatch(r'dna_r10\.4\.1_e8\.2_400bps_(sup|hac|fast)@v(\d+\.\d+\.\d+)', model.name)
    if not match:
        raise ValueError('Use the canonical Dorado R10.4.1 E8.2 400bps model directory name, including its version')
    if not re.fullmatch(re.escape(model.name) + r'_5mCG_5hmCG@v\d+(?:\.\d+)*', modified.name):
        raise ValueError('Modified model must be the matching versioned combined 5mCG_5hmCG model')
    if clair3 and not clair3_model and (match[1] != clair3 or match[2] != '5.0.0' or clair3 == 'fast'):
        raise ValueError('Bundled Clair3 requires a matching SUP/HAC Dorado v5.0.0 model and --basecall_model; other models require excluding Clair3/SubChrom')
    result = {'model': model_digest(model), 'modified_model': model_digest(modified)}
    if clair3_model:
        directory = Path(clair3_model)
        expected = f'r1041_e82_400bps_{clair3}_v{match[2].replace(".", "")}_with_mv'
        if clair3 not in ('sup', 'hac') or match[1] != clair3 or directory.name != expected:
            raise ValueError('External Clair3 model must match Dorado accuracy/version and --basecall_model, using the canonical _with_mv directory name')
        weights = {}
        for name in ('pileup.pt', 'full_alignment.pt'):
            path = directory / name
            if not path.is_file() or not path.stat().st_size:
                raise ValueError(f'Clair3 model missing nonempty {name}: {directory}')
            digest = hashlib.sha256()
            with path.open('rb') as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(block)
            weights[name] = digest.hexdigest()
        result['clair3_model'] = {'name': directory.name, 'sha256': weights, 'requires_moves': True}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--modified', required=True)
    parser.add_argument('--clair3')
    parser.add_argument('--clair3-model')
    args = parser.parse_args()
    result = validate(args.model, args.modified, args.clair3, args.clair3_model)
    version = subprocess.run(['dorado', '--version'], check=True, capture_output=True, text=True)
    result['dorado'] = (version.stdout + version.stderr).strip()
    help_result = subprocess.run(['dorado', 'basecaller', '--help'], check=True, capture_output=True, text=True)
    help_text = help_result.stdout + help_result.stderr
    for option in ['--modified-bases-models', '--no-trim', '--emit-moves', '--device']:
        if option not in help_text:
            raise ValueError(f'Installed Dorado lacks required basecaller option {option}')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
