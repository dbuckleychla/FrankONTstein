import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
try:
    import pysam
except ImportError:
    pysam = None

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'bin'))
if pysam: import adaptive_qc as qc

@unittest.skipUnless(pysam and shutil.which('samtools'), 'pysam and samtools required')
class QCTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.fasta=self.root/'ref.fa'; self.fasta.write_text('>chr1\n'+'CG'*50+'\n')
        pysam.faidx(str(self.fasta))
        self.enrichment=self.root/'enrichment.bed'; self.enrichment.write_text('chr1\t0\t10\tone\nchr1\t5\t15\ttwo\n')
        self.targets=self.root/'targets.bed'; self.targets.write_text('chr1\t5\t10\tgene\n')
        self.bam=self.root/'reads.bam'
        header={'HD':{'SO':'coordinate'},'SQ':[{'SN':'chr1','LN':100}]}
        with pysam.AlignmentFile(str(self.bam),'wb',header=header) as out:
            for name,start,n,mapq,flag,cigar in [('a',0,10,60,0,'10M'),('b',10,10,0,0,'10M'),('supp',10,10,60,2048,'10M'),('c',20,20,60,0,'10M5D10M'),('unmapped',-1,5,0,4,None)]:
                r=pysam.AlignedSegment();r.query_name=name;r.query_sequence='C'*n;r.flag=flag
                if start>=0:r.reference_id=0;r.reference_start=start;r.mapping_quality=mapq;r.cigarstring=cigar
                out.write(r)
        pysam.index(str(self.bam))
        self.bed=self.root/'mods.bed.gz'
        with gzip.open(self.bed,'wt') as out:
            for code,modified,other in [('m',3,2),('h',2,3)]:
                out.write(f'chr1\t0\t1\t{code}\t10\t.\t0\t1\t0\t10\t{modified*10}\t{modified}\t5\t{other}\t0\t0\t0\t0\n')
    def tearDown(self):self.tmp.cleanup()
    def test_exact_read_and_coverage_metrics(self):
        d=qc.bam_qc(str(self.bam),str(self.fasta),str(self.enrichment),str(self.targets),2)
        self.assertEqual(d['counts']['primary_reads'],4)
        self.assertEqual(d['alignment_rate'],.75)
        self.assertEqual(d['read_lengths']['all']['n50'],10)
        self.assertEqual(d['read_lengths']['all']['median'],10)
        self.assertEqual(d['on_enrichment_fraction_mapped'],2/3)
        self.assertEqual(d['coverage']['0']['enrichment']['bases'],15)
        self.assertEqual(d['coverage']['0']['genome']['aligned_bases'],40)
        self.assertEqual(d['coverage']['20']['genome']['aligned_bases'],30)
        self.assertEqual(d['coverage']['20']['enrichment']['aligned_bases'],10)
        self.assertEqual(d['coverage']['0']['genome']['breadth']['1'],.4)
    def test_cpg_denominators(self):
        d=qc.methylation_qc(str(self.bed),str(self.fasta),str(self.enrichment),str(self.targets))
        c=d['genome']['combined']
        self.assertEqual(c['sites'],1);self.assertEqual(c['valid'],10)
        self.assertEqual(c['mean_beta'],.5);self.assertEqual(c['reference_cpgs'],50)
        self.assertEqual(d['genome']['5mC']['weighted_beta'],.3)
        self.assertEqual(d['genome']['5hmC']['weighted_beta'],.2)
        self.assertEqual(d['targets']['combined']['sites'],0)
    def test_interval_union_and_boundaries(self):
        self.assertEqual(qc.merged([(0,10),(5,20),(20,30)]),[[0,30]])
        self.assertFalse(qc.Regions([(0,10)]).contains(10))
        self.targets.write_text('chr1\t99\t101\tbad\n')
        with self.assertRaises(ValueError):qc.read_bed(self.targets,{'chr1':100})
    def test_cli_and_parallel_methylation(self):
        raw=self.root/'plain.bed'
        with gzip.open(self.bed,'rt') as src: raw.write_text(src.read())
        pysam.tabix_compress(str(raw),str(self.bed),force=True)
        pysam.tabix_index(str(self.bed),preset='bed',force=True)
        serial=qc.methylation_qc(str(self.bed),str(self.fasta),str(self.enrichment),str(self.targets))
        parallel=qc.parallel_methylation(str(self.bed),str(self.fasta),str(self.enrichment),str(self.targets),2)
        self.assertEqual(serial,parallel)
        subprocess.run([sys.executable,str(ROOT/'bin/adaptive_qc.py'),'--sample','fixture','--bam',str(self.bam),'--fasta',str(self.fasta),'--targets',str(self.targets),'--enrichment',str(self.enrichment),'--bedmethyl',str(self.bed),'--threads','2'],cwd=self.root,check=True)
        data=json.loads((self.root/'qc/metrics.json').read_text())
        self.assertEqual(data['alignment']['counts']['primary_reads'],4)
        self.assertIn('fixture QC',(self.root/'qc/index.html').read_text())
        self.assertTrue((self.root/'qc/targets.tsv').exists())

    def test_primary_reference_names(self):
        for name in ['chr1','chrX','Y','NC_000001.11','NC_060925.1','NC_060948.1']:
            self.assertTrue(qc.primary_contig(name),name)
        for name in ['chrM','chr1_KI270706v1_random','NC_012920.1']:
            self.assertFalse(qc.primary_contig(name),name)

    def test_missing_hmc_and_empty_cpg_results(self):
        with gzip.open(self.bed,'wt') as out:
            out.write('chr1\t0\t1\tm\t10\t.\t0\t1\t0\t10\t30\t3\t7\t0\t0\t0\t0\t0\n')
        d=qc.methylation_qc(str(self.bed),str(self.fasta),str(self.enrichment),str(self.targets))
        self.assertFalse(d['genome']['5hmC']['available'])
        self.assertEqual(d['genome']['combined']['weighted_beta'],.3)
        with gzip.open(self.bed,'wt'): pass
        d=qc.methylation_qc(str(self.bed),str(self.fasta),str(self.enrichment),str(self.targets))
        self.assertIsNone(d['genome']['combined']['mean_beta'])
        raw=self.root/'empty.bed';raw.write_text('')
        pysam.tabix_compress(str(raw),str(self.bed),force=True)
        pysam.tabix_index(str(self.bed),preset='bed',force=True)
        self.assertEqual(d,qc.parallel_methylation(str(self.bed),str(self.fasta),str(self.enrichment),str(self.targets),2))

    def test_zero_metrics(self):
        self.assertIsNone(qc.lengths_summary({})['mean'])
        self.assertEqual(qc.depth_summary({},100)['histogram'],{0:100})
