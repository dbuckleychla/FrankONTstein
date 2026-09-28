"""Real indexed pileup test for target boundaries and off-region exclusion."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
try:
    import pysam
except ImportError:
    pysam = None

@unittest.skipUnless(pysam and shutil.which('bcftools'), 'pysam and bcftools required')
class TargetPileupTests(unittest.TestCase):
    def test_target_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref = root / 'reference.fa'
            ref.write_text('>chr1\n' + 'A' * 200 + '\n')
            pysam.faidx(str(ref))
            bam = root / 'reads.bam'
            with pysam.AlignmentFile(bam, 'wb', header={'HD': {'SO': 'coordinate'}, 'SQ': [{'SN': 'chr1', 'LN': 200}]}) as out:
                for start in (0, 100):
                    read = pysam.AlignedSegment()
                    read.query_name = f'read{start}'
                    read.query_sequence = 'A' * 50
                    read.query_qualities = pysam.qualitystring_to_array('I' * 50)
                    read.flag = 0
                    read.reference_id = 0
                    read.reference_start = start
                    read.mapping_quality = 60
                    read.cigarstring = '50M'
                    out.write(read)
            pysam.index(str(bam))
            (root / 'enrichment.bed').write_text('chr1\t0\t150\n')
            bed = root / 'targets.bed'
            bed.write_text('chr1\t10\t20\n')
            bcf = root / 'restricted.bcf'
            subprocess.run(['bcftools','mpileup','-Ob','--min-BQ','0','--threads','1',
                            '--regions-file',str(bed),'-f',str(ref),str(bam),'-o',str(bcf)],
                           check=True,capture_output=True,text=True)
            output = subprocess.check_output(['bcftools','query','-f','%POS\n',str(bcf)],text=True)
            self.assertEqual([int(p) for p in output.split()], list(range(11,21)))

if __name__ == '__main__':
    unittest.main()
