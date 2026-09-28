import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
try:
    import pysam
except ImportError:
    pysam=None

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'bin'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@unittest.skipUnless(pysam,'pysam required')
class VariantFinalizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.old=os.getcwd();os.chdir(self.root)
        self.mod=load('finalize_variants')
        Path('ref.fai').write_text('chr1\t100\t0\t100\t101\n')
    def tearDown(self):os.chdir(self.old);self.tmp.cleanup()
    def source(self,filters,chrom='chr1',sample='SAMPLE'):
        Path('input.vcf').write_text('##fileformat=VCFv4.2\n##FILTER=<ID=PASS,Description="Passed">\n##FILTER=<ID=LowQual,Description="Low quality">\n##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t'+sample+'\n'+''.join(f'{chrom}\t{i+1}\t.\tA\tC\t30\t{f}\t.\tGT\t0/1\n' for i,f in enumerate(filters)))
    def run_filter(self,caller='sniffles'):
        return self.mod.finalize('input.vcf','ref.fai','sample1','sample1.sv',caller)
    def test_only_explicit_pass_preserves_original_and_normalized(self):
        self.source(['PASS','LowQual','.']);original=Path('input.vcf').read_bytes()
        status=self.run_filter();self.assertEqual(status['pass_records'],1)
        with pysam.VariantFile('variants/sample1.sv.pass.vcf.gz') as v:
            self.assertEqual(list(v.header.samples),['sample1']);self.assertEqual([r.pos for r in v.fetch('chr1')],[1])
        with pysam.VariantFile('variants/sample1.sv.normalized.vcf.gz') as v:self.assertEqual(len(list(v)),3)
        self.assertEqual(Path('input.vcf').read_bytes(),original)
    def test_all_dot_does_not_invent_pass_records(self):
        self.source(['.','.']);status=self.run_filter()
        self.assertEqual(status['pass_filter_status'],'not_applicable_all_records_unassessed')
        self.assertFalse(Path('variants/sample1.sv.pass.vcf.gz').exists())
    def test_all_fail_has_valid_empty_pass_index(self):
        self.source(['LowQual']);self.run_filter()
        with pysam.VariantFile('variants/sample1.sv.pass.vcf.gz') as v:self.assertEqual(list(v.fetch()),[])
    def test_empty_callset(self):
        self.source([]);self.run_filter()
        with pysam.VariantFile('variants/sample1.sv.pass.vcf.gz') as v:self.assertEqual(list(v),[])
    def test_qdnaseq_contigs_and_sample_are_normalized(self):
        self.source(['PASS'],chrom='1',sample='offtarget');self.run_filter('qdnaseq')
        with pysam.VariantFile('variants/sample1.sv.pass.vcf.gz') as v:
            self.assertEqual(next(v.fetch('chr1')).contig,'chr1');self.assertEqual(v.header.contigs['chr1'].length,100)
    def test_ambiguous_multisample_input_fails(self):
        self.source(['PASS']);s=Path('input.vcf').read_text().replace('FORMAT\tSAMPLE','FORMAT\tbarcode01\tbarcode02').replace('\t0/1\n','\t0/1\t./.\n');Path('input.vcf').write_text(s)
        with self.assertRaisesRegex(ValueError,'Multi-sample VCF'):self.run_filter()
    def test_existing_expected_sample_can_be_selected(self):
        self.source(['PASS']);s=Path('input.vcf').read_text().replace('FORMAT\tSAMPLE','FORMAT\tsample1\tother').replace('\t0/1\n','\t0/1\t./.\n');Path('input.vcf').write_text(s);self.run_filter()
        with pysam.VariantFile('variants/sample1.sv.pass.vcf.gz') as v:self.assertEqual(list(v.header.samples),['sample1'])

if __name__=='__main__':unittest.main()
