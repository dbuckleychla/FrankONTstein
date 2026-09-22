#!/usr/bin/env python3
"""End-to-end routing contracts with stub data and mocked upstream tools.
Pass --nextflow-jar for environments with only a cached standalone distribution.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile

p=argparse.ArgumentParser()
p.add_argument('--nextflow-jar')
p.add_argument('--skip-resume-check', action='store_true', help='Routing only; explicitly skip cache validation')
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
command=['java','-jar',a.nextflow_jar] if a.nextflow_jar else ['nextflow']
with tempfile.TemporaryDirectory(prefix='frankontstein-contract-') as scratch:
    scratch=Path(scratch)
    subprocess.run(['python3','tests/make_contract_tools.py',str(scratch/'tools')],cwd=root,check=True)
    env=dict(os.environ, PATH=str(scratch/'tools')+os.pathsep+os.environ['PATH'])
    base=command+['run','.', '-stub-run','-profile','local','-ansi-log','false','--max_cpus','2','--max_memory','1 GB',
                  '--reference_bundle','tests/fixtures/bundle.json','--targets_bed','tests/fixtures/regions.bed',
                  '--enrichment_bed','tests/fixtures/regions.bed','--image_manifest','tests/fixtures/images.json']
    for tier,extra,expected in [
        ('primary',['--bam','tests/fixtures/stub.bam','--sample_id','sample1'],2),
        ('secondary',['--input','tests/fixtures/input.csv','--demux_samplesheet','tests/fixtures/demux.csv','--trim'],6),
        ('tertiary',['--bam','tests/fixtures/stub.bam','--sample_id','sample1'],13)]:
        out=scratch/tier
        args=base+['--'+tier,'--outdir',str(out),'-work-dir',str(scratch/'work'),*extra]
        if tier == 'primary':
            # Exercise the shared-input API; other tiers retain legacy-bundle coverage.
            index = args.index('--reference_bundle')
            del args[index:index+2]
            bundle = json.loads((root/'tests/fixtures/bundle.json').read_text())
            fixture = root/'tests/fixtures'
            args += ['--genome', bundle['genome'], '--fasta', str(fixture/bundle['fasta']),
                     '--fai', str(fixture/bundle['fai'])]
        subprocess.run(args,cwd=root,env=env,check=True)
        result=json.loads((out/'manifest.json').read_text())
        assert result['run']['stub'] is True
        assert len(result['analyses']) == expected, result['analyses']
        assert all(r['status']=='completed' for r in result['analyses'])
        if tier=='secondary': assert (out/'demultiplex/run1/demux/unclassified.bam').exists()
        if a.skip_resume_check: continue
        subprocess.run(args+['-resume',result['run']['session_id']],cwd=root,env=env,check=True)
        with (out/'pipeline_info/trace.tsv').open() as handle:
            statuses={r['status'] for r in csv.DictReader(handle,delimiter='\t') if not r['name'].endswith('RESULTS_INDEX')}
        assert statuses == {'CACHED'}, statuses
print('All three tier routing contracts passed (stub/mock tools only)' if a.skip_resume_check else 'All three tiers and resume contracts passed (stub/mock tools only)')
