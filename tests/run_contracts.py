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
    base=command+['run','.', '-stub-run','-profile','local','-ansi-log','false','--sequencing_kit','SQK-LSK114','--max_cpus','2','--max_memory','1 GB',
                  '--reference_bundle','tests/fixtures/bundle.json','--targets_bed','tests/fixtures/regions.bed',
                  '--enrichment_bed','tests/fixtures/regions.bed','--image_manifest','tests/fixtures/images.json']
    pooled = scratch/'pooled.csv'
    extra_bam = scratch/'second.bam'
    extra_bam.touch()
    pooled.write_text(f'sample,run,bam\npool,run1,{root}/tests/fixtures/stub.bam\npool,run1,{extra_bam}\n')
    for tier,extra,expected in [
        ('primary',['--bam','tests/fixtures/stub.bam','--sample_id','sample1'],5),
        ('secondary',['--input',str(pooled),'--demux_samplesheet','tests/fixtures/demux.csv'],12),
        ('tertiary',['--bam','tests/fixtures/stub.bam','--sample_id','sample1'],18)]:
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
        assert len(result.get('qc', [])) == (2 if tier == 'secondary' else 1)
        assert '.index.html' in (out/'index.html').read_text()
        assert len(result['analyses']) == expected, result['analyses']
        assert all(r['status']=='completed' for r in result['analyses'])
        for record in result['analyses']:
            assert all((out/path).exists() for path in record['files']), record
            sample = record['sample']
            assert (out/sample/'alignment'/f'{sample}.idxstats.txt').exists()
            assert not (out/sample/'variants').exists()
            assert all(sample in f.name for f in (out/sample).rglob('*') if f.is_file())
            if record['analysis'] in ['nasvar', 'ichorcna', 'subchrom']:
                analysis = record['analysis']
                directory = ('CNA/' + analysis) if analysis in ['ichorcna', 'subchrom'] else analysis
                assert not (out/sample/directory/analysis).exists()
                expected_file = {'nasvar': f'{sample}.result.json', 'ichorcna': f'{sample}.cnv.pdf', 'subchrom': f'{sample}.cnv.png'}[analysis]
                assert f'{sample}/{directory}/{expected_file}' in record['files'], record
            if record['analysis'] == 'qc':
                assert (out/sample/'qc'/f'{sample}.index.html').exists()
                assert not (out/sample/'qc/qc').exists()
            if record['analysis'] == 'bedmethyl':
                assert (out/sample/'methylation'/f'{sample}.cpg.bedmethyl.gz').exists()
                assert (out/sample/'methylation'/f'{sample}.cpg.bedmethyl.gz.tbi').exists()
            if record['analysis'] == 'methylation':
                sample = record['sample']
                assert record['files'] == [f'{sample}/methylation/classy'], record
                assert (out/sample/'methylation/classy'/f'{sample}_combined_classification.json').is_file()
                audit = out/sample/'methylation/classy'/f'{sample}.artifact_audit.json'
                assert json.loads(audit.read_text())['status'] == 'complete'
                assert (audit.parent/f'{sample}.artifact_audit.txt').is_file()
                assert not (out/sample/'methylation/methylation').exists()
        if tier=='tertiary':
            for caller in ('bcftools','clair3','clairsto','deepsomatic','sniffles','severus','stellerator','qdnaseq','delly'):
                category = 'germline' if caller in ('bcftools','clair3') else 'somatic' if caller in ('clairsto','deepsomatic') else 'CNA' if caller in ('qdnaseq','delly') else 'structural'
                assert list((out/'sample1'/category/caller).glob('*.pass.vcf.gz')), caller
                assert list((out/'sample1'/category/caller).glob('*.normalized.vcf.gz.tbi')), caller
                assert list((out/'sample1'/category/caller).glob('*.filtering.json')), caller
        if tier=='secondary':
            assert (out/'demultiplex/run1/input_00000001/unclassified.bam').exists()
            for barcode in ('barcode01', 'barcode02'):
                assert (out/f'demultiplex/run1/input_00000001/{barcode}/{barcode}.bam').exists()
            assert (out/'demultiplex/run1/input_00000002/unclassified.bam').exists()
            assert not (out/'demultiplex/run1/demux').exists()
        with (out/'pipeline_info/trace.tsv').open() as handle:
            names = [r['name'] for r in csv.DictReader(handle, delimiter='\t')]
        assert any(n.startswith('PRIMARY:ALIGN (') for n in names), names
        assert any(n.startswith('PRIMARY:TRIM_BAM (') for n in names), names
        assert any(n.startswith('PRIMARY:CLASSY_COMBINED (') for n in names), names
        if tier == 'secondary':
            assert sum(':TRIM_BAM (' in n for n in names) == 4, names
            assert any(n.startswith('SECONDARY:NASVAR (') for n in names), names
        if tier == 'tertiary':
            assert (out/'sample1/somatic/deepsomatic/sample1.somatic.vcf.gz.tbi').exists()
            assert (out/'sample1/somatic/deepsomatic/sample1.provenance.json').exists()
            assert any(n.startswith('TERTIARY:CALLING:DEEPSOMATIC (') for n in names), names
            assert any(n.startswith('TERTIARY:NASVAR (') for n in names), names
            assert any(n.startswith('TERTIARY:CALLING:SNIFFLES_CALL (') for n in names), names
            assert not any(n.startswith('SECONDARY:') for n in names), names
        if a.skip_resume_check: continue
        subprocess.run(args+['-resume',result['run']['session_id']],cwd=root,env=env,check=True)
        with (out/'pipeline_info/trace.tsv').open() as handle:
            statuses={r['status'] for r in csv.DictReader(handle,delimiter='\t') if not r['name'].endswith('RESULTS_INDEX')}
        assert statuses == {'CACHED'}, statuses
    # QC disabled still produces Classy and bedMethyl, with an explicit skipped record.
    out = scratch/'qc-disabled'
    args = base + ['--primary','--bam','tests/fixtures/stub.bam','--sample_id','sample1',
                   '--disable-qc','true','--no-trim-adapter','--outdir',str(out),'-work-dir',str(scratch/'disabled-work')]
    subprocess.run(args,cwd=root,env=env,check=True)
    data=json.loads((out/'manifest.json').read_text())
    assert any(r['analysis']=='qc' and r['status']=='skipped' for r in data['analyses'])
    assert not (out/'sample1/qc').exists()
    assert data.get('qc') == []
    with (out/'pipeline_info/trace.tsv').open() as handle:
        assert not any('TRIM_BAM' in r['name'] for r in csv.DictReader(handle, delimiter='\t'))
    with (out/'pipeline_info/trace.tsv').open() as handle:
        assert not any('SAMPLE_QC' in r['name'] for r in csv.DictReader(handle, delimiter='\t'))
    assert (out/'sample1/methylation/sample1.cpg.bedmethyl.gz').exists()
print('All three tier routing contracts passed (stub/mock tools only)' if a.skip_resume_check else 'All three tiers and resume contracts passed (stub/mock tools only)')
