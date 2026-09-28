#!/usr/bin/env python3
"""Resolve resource budgets and caps without scheduling infrastructure."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
PROBE='''workflow {
    def budgets = ['ALIGN':[32,64], 'PREPARE_BAM|TRIM_BAM':[4,8], 'DEMULTIPLEX':[8,8], 'SAMPLE_QC':[16,4], 'NASVAR':[2,8], 'CLASSY_COMBINED|MODKIT_PILEUP':[8,16], 'DEEPSOMATIC':[8,64]]
    budgets.each { name, expected ->
        def config = nextflow.Global.config.process.get('withName:' + name)
        def allocated = [:]
        ['cpus','memory'].each { directive ->
            def value = config[directive]
            def bound = value.rehydrate([task:[attempt:1], params:params], value.owner, value.thisObject)
            bound.resolveStrategy = Closure.DELEGATE_FIRST
            allocated[directive] = bound.call()
        }
        assert allocated.cpus == Math.min(expected[0], params.max_cpus as int)
        assert allocated.memory.toBytes() == Math.min(expected[1] * 1073741824L, (params.max_memory as nextflow.util.MemoryUnit).toBytes())
    }
}
'''
with tempfile.TemporaryDirectory(prefix='fot-resources-') as directory:
    scratch=Path(directory);probe=scratch/'probe.nf';probe.write_text(PROBE)
    env={k:v for k,v in os.environ.items() if not k.startswith('FRANKONTSTEIN_')};env['NXF_SYNTAX_PARSER']='v2'
    for profile in ('aws','slurm,apptainer','local,docker'):
        for cap in (8,32):
            cmd=['nextflow','-log',str(scratch/f'{profile}-{cap}.log'),'run',str(probe),'-profile',profile,
                 '--max_cpus',str(cap),'--max_memory',f'{cap*2} GB','--outdir',str(scratch/'out'),'-work-dir',str(scratch/'work')]
            result=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True)
            assert result.returncode==0,result.stdout+result.stderr
print('Resource budgets and CPU/RAM caps passed for AWS, Slurm and local (no tasks scheduled)')
