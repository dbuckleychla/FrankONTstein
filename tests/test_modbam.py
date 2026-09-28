import array
import json
import subprocess
import sys
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
    def test_required_moves(self):
        source = self.bam('no_moves.bam')
        with self.assertRaisesRegex(ValueError, 'Missing mv'):
            self.check.check(source, require_moves=True)
        for count in (6, 5):
            path = self.root / f'moves_{count}.bam'
            with pysam.AlignmentFile(source, 'rb') as src:
                read = next(src)
                read.set_tag('mv', array.array('b', [5] + [1] * count))
                with pysam.AlignmentFile(path, 'wb', header=src.header) as out:
                    out.write(read)
            self.check.check(path, require_moves=True)  # Presence only; no move-table decoding.

    def test_valid_modbam(self):
        self.assertEqual(self.check.check(self.bam('input.bam'),True)['modified_reads'],1)
    def run_check(self, path, threads):
        return subprocess.run([sys.executable, str(ROOT/'bin/check_bam.py'), str(path),
                               '--threads', str(threads)], text=True, capture_output=True)

    def test_bounded_check_never_reports_sample_as_full_yield(self):
        unmapped = self.bam('unmapped.bam')
        reverse = self.bam('reverse.bam', reverse=True)
        path = self.root/'mixed.bam'
        with pysam.AlignmentFile(unmapped, 'rb') as a, pysam.AlignmentFile(reverse, 'rb') as b:
            records = [next(a), next(b)]
            with pysam.AlignmentFile(path, 'wb', header=a.header) as out:
                for i in range(1100): out.write(records[i % 2])
        serial = self.run_check(path, 1)
        parallel = self.run_check(path, 3)
        self.assertEqual(serial.returncode, 0, serial.stderr)
        self.assertEqual(parallel.returncode, 0, parallel.stderr)
        self.assertEqual(json.loads(serial.stdout), json.loads(parallel.stdout))
        self.assertIsNone(json.loads(parallel.stdout)['reads'])
        self.assertEqual(json.loads(parallel.stdout)['sampled_reads'], 1000)
        self.assertFalse(json.loads(parallel.stdout)['exhaustive'])

    def test_trust_modification_encoding(self):
        source = self.bam('source.bam')
        path = self.root/'invalid.bam'
        with pysam.AlignmentFile(source, 'rb') as src:
            read = next(src)
            with pysam.AlignmentFile(path, 'wb', header=src.header) as out:
                for _ in range(600): out.write(read)
                read.query_name = 'bad_modifications'
                read.set_tag('MM', 'C+m,99,0;')
                out.write(read)
        for threads in [1, 3]:
            result = self.run_check(path, threads)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_parallel_rejects_invalid_worker_count(self):
        with self.assertRaisesRegex(ValueError, 'must be positive'):
            self.check.check('unused.bam', threads=0)
    def test_reject_missing_modifications(self):
        with self.assertRaises(ValueError): self.check.check(self.bam('missing.bam',tags=False))
    def test_trust_mn_encoding(self):
        self.check.check(self.bam('stale.bam',mn=9))  # Encoding validation belongs to methylation tools.

    def test_does_not_decode_modification_codes(self):
        source = self.bam('only_m.bam')
        self.check.check(source, require_cpg_modifications=True)
        path = self.root/'both.bam'
        with pysam.AlignmentFile(source, 'rb') as src:
            read = next(src)
            read.set_tag('MM', 'C+mh,0,0;')
            read.set_tag('ML', array.array('B', [200, 20, 100, 30]))
            with pysam.AlignmentFile(path, 'wb', header=src.header) as out:
                out.write(read)
        self.assertEqual(self.check.check(path, require_cpg_modifications=True)['modified_reads'], 1)
