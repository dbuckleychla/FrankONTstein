#!/usr/bin/env python3
"""Nextflow 26 caller-selection and failure contracts; stubs do not validate allele biology."""
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='fot-consensus-') as temp:
    temp=Path(temp)
    subprocess.run(['python3','tests/make_contract_tools.py',str(temp/'tools')],cwd=root,check=True)
    env=dict(os.environ, NXF_SYNTAX_PARSER='v2',PATH=str(temp/'tools')+os.pathsep+os.environ['PATH'])
    base=['nextflow','run','.', '-stub-run','-profile','local','-ansi-log','false','--sequencing_kit','SQK-LSK114',
          '--bam','tests/fixtures/stub.bam','--sample_id','S','--max_cpus','2','--max_memory','1 GB','--max_retries','0',
          '--reference_bundle','tests/fixtures/bundle.json','--targets_bed','tests/fixtures/regions.bed',
          '--enrichment_bed','tests/fixtures/regions.bed','--image_manifest','tests/fixtures/images.json','--tertiary']
    for name,extra,expect in [('pair',['--callers','deepsomatic,clairsto','--disable_qc'],True),
                              ('single',['--callers','deepsomatic'],False)]:
        out=temp/name
        subprocess.run(base+extra+['--outdir',str(out),'-work-dir',str(temp/(name+'-work'))],cwd=root,env=env,check=True)
        manifest=json.loads((out/'manifest.json').read_text())
        assert any(r['analysis']=='consensus' for r in manifest['analyses'])==expect
        assert (out/'S/summary/S.summary.html').exists()
    # hs1 default excludes DeepSomatic; no consensus should be scheduled.
    bundle=json.loads((root/'tests/fixtures/bundle.json').read_text())
    def absolute(v):
        if isinstance(v,dict):return {k:absolute(x) if k not in ['id','genome','schema_version','models'] else x for k,x in v.items()}
        return str(root/'tests/fixtures'/v) if isinstance(v,str) else v
    bundle=absolute(bundle);bundle['genome']='hs1';b=temp/'hs1.json';b.write_text(json.dumps(bundle))
    args=base.copy();args[args.index('--reference_bundle')+1]=str(b);out=temp/'hs1'
    subprocess.run(args+['--outdir',str(out),'-work-dir',str(temp/'hs1-work')],cwd=root,env=env,check=True)
    with (out/'pipeline_info/trace.tsv').open() as f:trace=list(csv.DictReader(f,delimiter='\t'))
    assert not any('SOMATIC_CONSENSUS' in r['name'] for r in trace)
    for process,analysis in [('SOMATIC_CONSENSUS','consensus'),('SAMPLE_SUMMARY','summary')]:
        cfg=temp/'fail.config';cfg.write_text('process { withName: '+process+" { beforeScript = 'exit 23' } }\n")
        out=temp/process
        result=subprocess.run(base+['--callers','deepsomatic,clairsto','-c',str(cfg),'--outdir',str(out),'-work-dir',str(temp/(process+'-work'))],cwd=root,env=env,capture_output=True,text=True)
        assert result.returncode!=0
        rows=json.loads((out/'manifest.json').read_text())['analyses']
        assert next(r for r in rows if r['analysis']==analysis)['status']=='failed',rows
print('Consensus caller selection, hs1, disabled QC, and failure contracts passed (stubs).')
