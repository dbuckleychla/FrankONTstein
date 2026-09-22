import array
import importlib.util
from pathlib import Path
import tempfile
import unittest
try:
    import pysam
except ImportError:
    pysam = None

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'bin'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

@unittest.skipUnless(pysam, 'pysam required for real BAM integrity tests')
class ModbamTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.check=load('check_bam')
        self.compare=load('compare_modbam')
    def tearDown(self): self.temp.cleanup()
    def bam(self,name,reverse=False,probabilities=(200,100),tags=True,mn=6,read_id='read1'):
        path=self.root/name
        header={'HD':{'VN':'1.6'},'SQ':[{'SN':'chr1','LN':100}], 'RG':[{'ID':'run1','SM':'s1'}]}
        read=pysam.AlignedSegment();read.query_name=read_id
        read.query_sequence='CGACGT' if reverse else 'ACGTCG'
        read.flag=16 if reverse else 4
        read.set_tag('RG','run1')
        if reverse:
            read.reference_id=0;read.reference_start=10;read.cigarstring='6M';read.mapping_quality=60
        if tags:
            read.set_tag('MM','C+m,0,0;');read.set_tag('ML',array.array('B',probabilities));read.set_tag('MN',mn)
        with pysam.AlignmentFile(path,'wb',header=header) as out: out.write(read)
        return path
    def test_valid_modbam(self):
        self.assertEqual(self.check.check(self.bam('input.bam'),True)['modified_reads'],1)
    def test_reject_missing_modifications(self):
        with self.assertRaises(ValueError): self.check.check(self.bam('missing.bam',tags=False))
    def test_reject_stale_trim_coordinates(self):
        with self.assertRaises(ValueError): self.check.check(self.bam('stale.bam',mn=9))
    def test_reverse_alignment_preserves_modifications(self):
        self.compare.compare(self.bam('before.bam'),self.bam('after.bam',reverse=True),self.root/'compare.db')
    def test_detect_changed_probability(self):
        with self.assertRaises(ValueError):
            self.compare.compare(self.bam('before.bam'),self.bam('after.bam',reverse=True,probabilities=(1,100)),self.root/'compare.db')
    def test_detect_lost_tags(self):
        with self.assertRaises(ValueError):
            self.compare.compare(self.bam('before.bam'),self.bam('after.bam',tags=False),self.root/'compare.db')
    def test_detect_unknown_reads(self):
        with self.assertRaises(ValueError):
            self.compare.compare(self.bam('before.bam'),self.bam('after.bam',read_id='other'),self.root/'compare.db')
