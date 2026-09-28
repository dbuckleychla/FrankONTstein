import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
from prepare_reference_assets import prepare
from audit_classy import audit

class MitigationTests(unittest.TestCase):
    def test_repeat_aliases_exclusions_and_duplicate_targets_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)
            (r/'ref.fai').write_text('chr1\t100\t0\t100\t101\n')
            (r/'reference.json').write_text(json.dumps({'contigs':[{'name':'chr1','accession':'NC_1'}]}))
            (r/'repeats.bed').write_text('NC_1\t0\t10\nabsent\t1\t3\n')
            target='chrX\t0\t2\tCRLF2\nchrY\t0\t2\tCRLF2\n';(r/'targets.bed').write_text(target)
            result=prepare(r/'ref.fai',r)
            self.assertEqual((r/'repeats.bed').read_text(),'chr1\t0\t10\n')
            self.assertEqual(result['repeats_excluded'],1)
            self.assertEqual(result['ambiguous_target_names'],{'CRLF2':['chrX','chrY']})
            self.assertEqual((r/'targets.bed').read_text(),target)
            self.assertEqual((r/'repeats.excluded.bed').read_text(),'absent\t1\t3\n')
    def test_missing_classy_figures_surface_without_removing_results(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);p=r/'combined.json';p.write_text(json.dumps({'result':{'probability':0.9},'charts':['classy/present.svg','classy/missing.svg']}))
            (r/'present.svg').write_text('<svg/>');original=p.read_bytes();result=audit(p)
            self.assertEqual(result['missing_sidecars'],['missing.svg']);self.assertEqual(p.read_bytes(),original)

if __name__=='__main__':unittest.main()

class HeaderTests(unittest.TestCase):
    def test_sample_reheader_preserves_read_group_ids_and_modification_tags(self):
        import array
        import pysam
        from bam_sample_header import sample_header
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory);source=r/'input.bam'
            header={'HD':{'VN':'1.6'},'SQ':[{'SN':'chr1','LN':100}], 'RG':[{'ID':'run.barcode03','SM':'barcode03'},{'ID':'unused','SM':'barcode04'}]}
            read=pysam.AlignedSegment();read.query_name='r';read.query_sequence='ACG';read.flag=4
            read.set_tag('RG','run.barcode03');read.set_tag('MM','C+m,0;');read.set_tag('ML',array.array('B',[200]));read.set_tag('MN',3)
            with pysam.AlignmentFile(source,'wb',header=header) as out:out.write(read)
            h=pysam.AlignmentHeader.from_text(sample_header(source,'sample1'))
            self.assertEqual([g['ID'] for g in h.to_dict()['RG']],['run.barcode03','unused'])
            self.assertEqual({g['SM'] for g in h.to_dict()['RG']},{'sample1'})
            header_path=r/'header.sam';header_path.write_text(str(h))
            pysam.samtools.reheader(str(header_path),str(source),save_stdout=str(r/'output.bam'))
            with pysam.AlignmentFile(r/'output.bam','rb') as bam:
                found=next(bam);self.assertEqual(found.get_tags(),read.get_tags())
                self.assertEqual(found.query_sequence,read.query_sequence)
