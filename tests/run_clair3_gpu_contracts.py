#!/usr/bin/env python3
"""Resolve caller GPU directives without scheduling jobs or requiring a GPU."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROBE = '''workflow {
    def gpu = WorkflowPlan.clair3Gpu(params as Map, workflow.profile)
    assert gpu == params.expected_gpu.toString().toBoolean()
    WorkflowPlan.validateClair3Gpu(params as Map, workflow.profile)
    ['CLAIR3', 'CLAIRS_TO_CALL', 'DEEPSOMATIC'].each { caller ->
    assert !WorkflowPlan.clairstoGpu(params as Map, workflow.profile)
    def callerGpu = caller == 'CLAIRS_TO_CALL' ? false : gpu
    assert WorkflowPlan.deepsomaticGpu(params as Map, workflow.profile) == gpu
    def config = nextflow.Global.config.process.get('withName:' + caller)
    def containerOptions = config.containerOptions.rehydrate([workflow:workflow, params:params], config.containerOptions.owner, config.containerOptions.thisObject)
    containerOptions.resolveStrategy = Closure.DELEGATE_FIRST
    if (workflow.profile == 'aws') {
        assert config.queue.call() == (callerGpu ? 'gpu' : 'cpu')
        assert config.accelerator.call() == (callerGpu ? 1 : null)
    } else if (workflow.profile.contains('slurm')) {
        assert config.queue.call() == (callerGpu ? 'gpu' : 'cpu')
        assert config.clusterOptions.call().contains('--gres=gpu:1') == callerGpu
        assert containerOptions.call() == (callerGpu ? '--nv' : '')
    } else {
        assert containerOptions.call() == (callerGpu ? '--gpus device=0' : '')
    }
    }
}
'''
with tempfile.TemporaryDirectory(prefix='clair3-gpu-') as directory:
    scratch = Path(directory)
    probe = scratch / 'probe.nf'
    probe.write_text(PROBE)
    env = {k:v for k,v in os.environ.items() if not k.startswith('FRANKONTSTEIN_')}
    env['NXF_SYNTAX_PARSER'] = 'v2'
    cases = [
        ('aws', ['--aws_queue','cpu','--aws_gpu_queue','gpu','--aws_region','us-west-2']),
        ('slurm,apptainer', ['--slurm_queue','cpu','--gpu_queue','gpu']),
        ('local,docker', ['--basecall_device','0']),
    ]
    for index, (profile, options) in enumerate(cases):
        for override in (False, True):
            extra = ['--clair3_gpu','false','--clairsto_gpu','false','--deepsomatic_gpu','false'] if override else []
            command = ['nextflow','-log',str(scratch / f'{index}-{override}.log'),
                       'run',str(probe),'-lib',str(ROOT / 'lib'),'-profile',profile,
                       '--outdir',str(scratch / 'results'),'-work-dir',str(scratch / 'work'),
                       '--expected_gpu',str(not override).lower(),*options,*extra]
            result = subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
            assert result.returncode == 0, result.stdout + result.stderr
print('Clair3/DeepSomatic GPU routing, ClairS-TO CPU default and CPU overrides passed for AWS, Slurm and local (no tasks)')
