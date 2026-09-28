from array import array
import importlib.util
from pathlib import Path
import tempfile
import unittest
import pysam

spec=importlib.util.spec_from_file_location('demux_qc',Path(__file__).parents[1]/'bin/demux_qc.py')
qc=importlib.util.module_from_spec(spec)
spec.loader.exec_module(qc)

header_spec=importlib.util.spec_from_file_location('cat_header',Path(__file__).parents[1]/'bin/cat_bam_header.py')
cat_header=importlib.util.module_from_spec(header_spec)
header_spec.loader.exec_module(cat_header)

class DemuxShardCounts(unittest.TestCase):
    def test_repeated_barcode_names_are_summed(self):
        with tempfile.TemporaryDirectory() as directory:
            paths=[]
            for shard, size in [('first',2),('second',3)]:
                path=Path(directory)/shard/'barcode01.bam'
                path.parent.mkdir()
                with pysam.AlignmentFile(path,'wb',header={'HD':{'VN':'1.6'},'RG':[{'ID':'run','SM':'pool'}]}) as bam:
                    for i in range(size):
                        read=pysam.AlignedSegment()
                        read.query_name=f'{shard}-{i}'
                        read.query_sequence='ACG'
                        read.flag=4
                        read.set_tag('RG','run')
                        read.set_tag('MM','C+m,0;')
                        read.set_tag('ML',array('B',[220]))
                        read.set_tag('MN',3)
                        read.set_tag('mv',array('b',[5,1,1,1]))
                        bam.write(read)
                paths.append(path)
            self.assertEqual(qc.aggregate(map(qc.count,paths)), {'barcode01.bam':{'reads':5,'bases':15}})

            # The post-demux merge must retain every read and its modification,
            # move-table and read-group metadata even with repeated RG IDs.
            merged=Path(directory)/'prepared.bam'
            header, provenance=cat_header.combined_header(paths)
            header_path=Path(directory)/'header.sam'
            header_path.write_text(header)
            pysam.cat('-h',str(header_path),'-o',str(merged),*[str(p) for p in paths])
            with pysam.AlignmentFile(merged,'rb',check_sq=False) as bam:
                groups={rg['ID'] for rg in bam.header.to_dict()['RG']}
                reads=list(bam.fetch(until_eof=True))
                self.assertEqual(len(reads),5)
                self.assertEqual(len({r.query_name for r in reads}),5)
                for read in reads:
                    self.assertIn(read.get_tag('RG'),groups)
                    self.assertEqual(read.get_tag('MM'),'C+m,0;')
                    self.assertEqual(list(read.get_tag('ML')),[220])
                    self.assertEqual(read.get_tag('MN'),3)
                    self.assertEqual(list(read.get_tag('mv')),[5,1,1,1])

    def test_header_union_and_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            def write(name, rg, command, length=100):
                path=Path(directory)/name
                with pysam.AlignmentFile(path,'wb',header={'HD':{'VN':'1.6'},'SQ':[{'SN':'chr1','LN':length}],
                        'RG':[rg], 'PG':[{'ID':'dorado','PN':'dorado','VN':'1.3','CL':command}]}) as bam:
                    pass
                return path
            a=write('a.bam',{'ID':'rg1','SM':'sample'},'trim a.bam')
            b=write('b.bam',{'ID':'rg2','SM':'sample'},'trim b.bam')
            text, provenance=cat_header.combined_header([a,b])
            header=pysam.AlignmentHeader.from_text(text).to_dict()
            self.assertEqual([r['ID'] for r in header['RG']],['rg1','rg2'])
            self.assertNotIn('CL',header['PG'][0])
            self.assertEqual(provenance['inputs'][1]['header']['PG'][0]['CL'],'trim b.bam')
            conflict=write('conflict.bam',{'ID':'rg1','SM':'different'},'trim conflict.bam')
            with self.assertRaisesRegex(ValueError,'Conflicting @RG'):
                cat_header.combined_header([a,conflict])
            other=write('other.bam',{'ID':'rg3','SM':'sample'},'trim other.bam',200)
            with self.assertRaisesRegex(ValueError,'sequence dictionaries'):
                cat_header.combined_header([a,other])
