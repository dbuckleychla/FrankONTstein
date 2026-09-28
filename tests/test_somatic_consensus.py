import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
try:
    import pysam
except ImportError:
    pysam=None
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
if pysam:
    import somatic_consensus as sc


@unittest.skipUnless(pysam,'pysam required')
class ConsensusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name)
        self.fa=self.r/'ref.fa';self.fa.write_text('>chr1\n'+'A'*100+'\n');pysam.faidx(str(self.fa));self.fai=str(self.fa)+'.fai'
        self.ref=self.r/'reference.json';self.ref.write_text(json.dumps({'contigs':[{'name':'chr1','accession':'NC_1'}]}))
        self.cfg=self.r/'pipeline.json'
        cfg={'genes': {'snv': {'pathogenic':['P','N'], 'pharmacogenomics':['PGX'], 'transcripts': {
            'P': {'transcript':'p','variants':{'query':[2,12]}},
            'N': {'transcript':'n','variants':{'query':[2,12]}}}},
            'itd': {'I': {'chrom':'NC_1','start':1,'end':10}}}}
        self.cfg.write_text(json.dumps(cfg))
        self.gff=self.r/'genes.gff';self.gff.write_text('\n'.join([
            'NC_1\t.\tgene\t1\t30\t.\t+\t.\tID=gp;Name=P','NC_1\t.\tmRNA\t1\t30\t.\t+\t.\tID=p;Parent=gp',
            'NC_1\t.\tCDS\t1\t10\t.\t+\t0\tParent=p','NC_1\t.\tCDS\t21\t30\t.\t+\t0\tParent=p',
            'NC_1\t.\tgene\t41\t70\t.\t-\t.\tID=gn;Name=N','NC_1\t.\tmRNA\t41\t70\t.\t-\t.\tID=n;Parent=gn',
            'NC_1\t.\tCDS\t41\t50\t.\t-\t0\tParent=n','NC_1\t.\tCDS\t61\t70\t.\t-\t0\tParent=n'])+'\n')
    def tearDown(self):self.tmp.cleanup()
    def vcf(self,name,rows,sample='S'):
        p=self.r/(name+'.vcf');p.write_text('##fileformat=VCFv4.2\n##contig=<ID=chr1,length=100>\n##FILTER=<ID=LowQual,Description="low">\n##FORMAT=<ID=GT,Number=1,Type=String,Description="GT">\n##FORMAT=<ID=DP,Number=1,Type=Integer,Description="DP">\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t'+sample+'\n'+''.join(f'chr1\t{pos}\t.\t{ref}\t{alt}\t30\t{flt}\t.\tGT:DP\t0/1:20\n' for pos,ref,alt,flt in rows));return p
    def run_consensus(self,a,b):
        return sc.consensus('S',{'deepsomatic':[a],'clairsto':[b]},self.fa,self.fai,self.cfg,self.gff,self.ref,self.r/'out')
    def test_mapping_strand_exon_and_alias(self):
        q=sc.resolve_queries(self.cfg,self.gff,self.ref,self.fai)
        self.assertEqual({(x['gene'],x.get('cds_position')):x['start']+1 for x in q if x['kind']=='snv'}, {('P',2):2,('P',12):22,('N',2):69,('N',12):49})
    def test_normalization_duplicates_multiallelic_and_pass(self):
        a=self.vcf('a',[(2,'A','C,G','PASS'),(2,'A','C','PASS'),(6,'AA','A','PASS'),(22,'A','C','.'),(49,'A','C','PASS'),(69,'A','C','PASS')])
        b=self.vcf('b',[(2,'A','C','PASS'),(8,'AA','A','PASS'),(22,'A','C','PASS'),(49,'A','C','LowQual'),(69,'A','G','PASS')])
        d=self.run_consensus(a,b);self.assertEqual(d['counts'],{'snv':1,'indel':1})
        self.assertEqual(len([r for r in d['evidence'] if r['pos']==2 and r['alt']=='C']),1)
        for kind in ['snv','indel']:
            with pysam.VariantFile(str(self.r/'out'/f'S.consensus.{kind}.vcf.gz')) as v:
                rec=next(v.fetch());self.assertEqual(rec.samples['S']['GT'],(None,None));self.assertIsNone(rec.qual)
                self.assertEqual(list(rec.filter),['PASS'])
        self.assertEqual(next(r['pos'] for r in d['evidence'] if r['kind']=='indel'),1)
    def test_empty_and_missing_or_mismatched_inputs(self):
        a=self.vcf('a',[]);b=self.vcf('b',[]);self.assertEqual(self.run_consensus(a,b)['counts'],{'snv':0,'indel':0})
        with self.assertRaises(ValueError):self.run_consensus(a,self.vcf('bad',[],sample='OTHER'))
        cfg=json.loads(self.cfg.read_text());cfg['genes']['snv']['transcripts']['P']['transcript']='absent';self.cfg.write_text(json.dumps(cfg))
        with self.assertRaises(ValueError):self.run_consensus(a,b)
    def test_reference_mismatch_and_unsupported(self):
        with self.assertRaises(Exception):self.run_consensus(self.vcf('a',[(2,'C','G','PASS')]),self.vcf('b',[]))
        d=self.run_consensus(self.vcf('a',[(2,'AA','CC','PASS'),(2,'A','CG','PASS'),(2,'A','<DEL>','PASS')]),self.vcf('b',[]))
        self.assertEqual(d['counts']['snv'],0);self.assertTrue(d['excluded_records'])
    def test_indel_boundary_anchor(self):
        cfg=json.loads(self.cfg.read_text());cfg['genes']['itd']['I'].update(start=10,end=10);self.cfg.write_text(json.dumps(cfg))
        a=self.vcf('a',[(10,'A','AC','PASS'),(11,'A','AC','PASS')]);d=self.run_consensus(a,a)
        self.assertEqual(d['counts']['indel'],1);self.assertEqual(d['evidence'][0]['pos'],10)


if __name__=='__main__':unittest.main()
