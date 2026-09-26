#!/usr/bin/env python3
"""Emit shell exports for Nextflow from Terraform outputs; never launch or apply."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
AWS_PARAMS = ('aws_region', 'aws_queue', 'aws_gpu_queue', 'aws_job_role',
              'aws_logs_group', 'aws_cli_path')


def read_outputs(terraform_dir, outputs_file=None):
    if outputs_file:
        return json.loads(Path(outputs_file).read_text())
    result = subprocess.run(
        ['terraform', f'-chdir={terraform_dir}', 'output', '-json'],
        check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def setting(outputs, name):
    entry = outputs.get(name)
    if not isinstance(entry, dict) or 'value' not in entry:
        raise ValueError(f'Missing Terraform output {name}; use the full terraform output -json export')
    return entry['value']


def s3_prefix(value, name):
    if not isinstance(value, str):
        raise ValueError(f'Terraform {name} must be an S3 URI')
    uri = urlsplit(value)
    if uri.scheme != 's3' or not uri.netloc or uri.query or uri.fragment:
        raise ValueError(f'Terraform {name} must be an S3 URI')
    return value.rstrip('/')


def build_environment(outputs, run_id):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', run_id):
        raise ValueError('--run-id must start with a letter/digit and contain only letters, digits, dots, underscores or hyphens')
    if not isinstance(outputs, dict):
        raise ValueError('Terraform outputs must be a JSON object')
    params = setting(outputs, 'nextflow_params')
    if not isinstance(params, dict):
        raise ValueError('Terraform nextflow_params must be an object')
    for name in ('aws_region', 'aws_queue', 'aws_job_role'):
        if not isinstance(params.get(name), str) or not params[name].strip():
            raise ValueError(f'Terraform nextflow_params.{name} is missing or empty')
    work = s3_prefix(setting(outputs, 'work_dir'), 'work_dir')
    out = s3_prefix(params.get('outdir'), 'nextflow_params.outdir')
    environment = {}
    for name in AWS_PARAMS:
        value = params.get(name)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f'Terraform nextflow_params.{name} must be a nonempty string or null')
        # Explicit empty exports clear values left by a previous stack/session.
        environment['FRANKONTSTEIN_' + name.upper()] = value or ''
    environment['FRANKONTSTEIN_OUTDIR'] = f'{out}/{run_id}'
    environment['FRANKONTSTEIN_WORK_DIR'] = f'{work}/{run_id}'
    return environment


def shell_exports(environment):
    return '\n'.join(f'export {name}={shlex.quote(value)}' for name, value in environment.items()) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Load into bash/zsh with: AWS_BATCH_ENV="$(python3 bin/aws_batch_env.py --run-id run1)" '
        '&& eval "$AWS_BATCH_ENV". Or redirect stdout to a file and source it.'))
    parser.add_argument('--run-id', required=True, help='Suffix for Terraform output/work prefixes; reuse it with -resume')
    parser.add_argument('--terraform-dir', type=Path, default=ROOT / 'terraform/aws',
                        help='Initialized Terraform directory with the intended state/workspace')
    parser.add_argument('--terraform-outputs', type=Path,
                        help='Saved full terraform output -json export; skips invoking Terraform')
    args = parser.parse_args()
    try:
        outputs = read_outputs(args.terraform_dir, args.terraform_outputs)
        environment = build_environment(outputs, args.run_id)
        # Stdout is exclusively shell-safe exports. A child cannot set its parent's environment.
        print(shell_exports(environment), end='')
    except subprocess.CalledProcessError as error:
        print('Cannot read Terraform outputs; verify the initialized backend, workspace and AWS credentials. No exports were emitted.', file=sys.stderr)
        if error.stderr:
            print(error.stderr.strip(), file=sys.stderr)
        return error.returncode or 1
    except (OSError, ValueError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
