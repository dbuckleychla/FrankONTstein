import base64
import re
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import report_presentation as rp
import sample_summary as ss

class PresentationTests(unittest.TestCase):
    def test_rounding_and_missing(self):
        self.assertEqual(rp.number(1234567.89),'1,234,568')
        self.assertEqual(rp.number(2.345,1),'2.3')
        self.assertEqual(rp.number(.00001,percent=True),'<0.1%')
        self.assertEqual(rp.number(0,percent=True),'0.0%')
        self.assertEqual(rp.number(None),'Unavailable')
        self.assertEqual(rp.number(float('nan')),'Unavailable')
    def test_histogram_counts_and_offline_escaping(self):
        pts=rp.hist_points({'100':3,'1000':1},True,True)
        self.assertEqual(sum(y for x,y in pts),100)
        output=rp.chart('<bad>',[('test',pts)],'bp','%',True,histogram=True)
        self.assertNotIn('<bad>',output)
        svg=base64.b64decode(re.search('base64,([^\"]+)',output)[1]).decode()
        self.assertIn('<rect',svg);self.assertIn('&lt;bad&gt;',svg)
    def test_legacy_qc_does_not_infer_target_metrics(self):
        output=rp.qc_content({'alignment':{'read_lengths':{'on_enrichment':{'reads':3,'bases':300,'mean':100,'median':100,'n50':100}}}})
        self.assertIn('On target</td><td>Unavailable',output)
        self.assertIn('comparisons overlap',output)
    def test_nasvar_structured_results_and_empty_status(self):
        data={'sample':'S','nasvar':{'cnv':{'genes':{'GENE':{'focal':1.23456,'local':2}}},'fusions':{'fusions':[]}},'fusions':{'candidates':[]},'figures':[]}
        result=ss.nasvar_sections(data)
        self.assertIn('Focal copy number',result);self.assertIn('1.23',result)
        self.assertNotIn('1.23456',result)
        self.assertIn('No NASVAR fusion candidates',ss.fusion_table(data))
        data['nasvar']={}
        self.assertIn('unavailable',ss.fusion_table(data))

class SimplifiedReportTests(unittest.TestCase):
    def test_one_methylation_histogram(self):
        mods={m:{'available':True,'beta_hist':{'0':1,'50':2,'99':1},'beta_hist_depth10':{'50':2},'depth_hist':{'10':4}} for m in ['5mC','5hmC']}
        output=rp.qc_content({'methylation':{'genome':mods,'targets':mods}})
        self.assertEqual(output.count('<h3>5mCpG beta distribution</h3>'),1)
        self.assertNotIn('Beta at depth',output)
        self.assertNotIn('Valid modification depth',output)
    def test_fusion_summary_uses_total_not_breakpoint_sum(self):
        row=ss.fusion_summary_row({'source':'NASVAR','evidence':{'gene1':{'name':'PML','chr':'chr15','pos':10},'gene2':{'name':'RARA','chr':'chr17','pos':20},'supporting_reads':49,'breakpoints':[{'n_reads':22},{'n_reads':27},{'n_reads':26}]}})
        self.assertEqual(row,['NASVAR','PML::RARA','chr15:10','chr17:20',49])
        other=ss.fusion_summary_row({'source':'Stellerator','evidence':{'gene1':'PML','gene2':'RARA','chr1':'chr15','pos1':'10','chr2':'chr17','pos2':'20','supporting_reads':'12'}})
        self.assertEqual(other,['Stellerator','PML::RARA','chr15:10','chr17:20',12])
        other=ss.fusion_summary_row({'source':'Stellerator','evidence':{'gene1':'A','gene2':'B'}})
        self.assertIsNone(other[-1])
    def test_gc_plots_omitted(self):
        output=ss.nasvar_sections({'sample':'S','nasvar':{'fusions':{'fusions':[]}},'figures':[{'name':'S.gc_vs_coverage.svg','data':'test'}]})
        self.assertNotIn('<img',output)
