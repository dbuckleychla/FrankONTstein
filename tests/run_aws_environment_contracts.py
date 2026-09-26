#!/usr/bin/env python3
"""Check AWS environment defaults and precedence without submitting AWS jobs."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROBE = '''workflow {
    assert params.aws_queue == params.expected_queue
    assert nextflow.Global.config.process.queue == params.expected_queue
    assert params.outdir == params.expected_outdir
    assert workflow.workDir.toString() == params.expected_workdir
    // Construct an actual nf-amazon S3 Path without reading/writing remote objects.
    def remoteWork = file('s3://example-bucket/work/run')
    assert remoteWork.toUri().scheme == 's3'
    assert !remoteWork.toString().startsWith('s3://')
    WorkflowPlan.validateAws(params as Map, remoteWork)
    try {
        WorkflowPlan.validateAws(params as Map, workflow.workDir)
        assert false : 'Local work directory must be rejected'
    } catch (IllegalArgumentException fault) {
        assert fault.message == 'AWS requires: -work-dir s3://... (or FRANKONTSTEIN_WORK_DIR)'
    }
    try {
        WorkflowPlan.validateAws([aws_region:'us-west-2'], remoteWork)
        assert false : 'Missing queue and role must be rejected'
    } catch (IllegalArgumentException fault) {
        assert fault.message == 'AWS requires: --aws_queue, --aws_job_role'
    }
}
'''


def run(command, env):
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


with tempfile.TemporaryDirectory(prefix='frankontstein-aws-env-') as directory:
    scratch = Path(directory)
    script = scratch / 'probe.nf'
    script.write_text(PROBE)
    base = {k:v for k,v in os.environ.items() if not k.startswith('FRANKONTSTEIN_')}
    base.update(NXF_SYNTAX_PARSER='v2', FRANKONTSTEIN_AWS_REGION='us-west-2',
                FRANKONTSTEIN_AWS_QUEUE='environment-cpu', FRANKONTSTEIN_AWS_GPU_QUEUE='environment-gpu',
                FRANKONTSTEIN_AWS_JOB_ROLE='test-role')
    for case in ['defaults', 'cli', 'params-file']:
        env = dict(base, FRANKONTSTEIN_OUTDIR=str(scratch / (case + '-env-out')),
                   FRANKONTSTEIN_WORK_DIR=str(scratch / (case + '-env-work')))
        queue, out, work = 'environment-cpu', env['FRANKONTSTEIN_OUTDIR'], env['FRANKONTSTEIN_WORK_DIR']
        extra = []
        if case == 'cli':
            queue, out, work = 'cli-cpu', str(scratch / 'cli-out'), str(scratch / 'cli-work')
            extra = ['--aws_queue', queue, '--outdir', out, '-work-dir', work]
        elif case == 'params-file':
            queue, out = 'file-cpu', str(scratch / 'file-out')
            params = scratch / 'overrides.json'
            params.write_text(json.dumps({'aws_queue': queue, 'outdir': out}))
            extra = ['-params-file', str(params)]
        run(['nextflow', '-log', str(scratch / (case + '.log')), 'run', str(script), '-lib', str(ROOT / 'lib'), '-profile', 'aws', '-ansi-log', 'false',
             '--expected_queue', queue, '--expected_outdir', out, '--expected_workdir', work, *extra], env)
    local = run(['nextflow', 'config', '-profile', 'local', '-flat'], env)
    assert 'environment-cpu' not in local
    assert env['FRANKONTSTEIN_OUTDIR'] not in local and env['FRANKONTSTEIN_WORK_DIR'] not in local
print('AWS environment defaults, CLI/params-file precedence and local-profile isolation passed (no AWS jobs)')
