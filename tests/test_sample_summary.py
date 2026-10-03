import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
import sample_summary as ss

class SummaryTests(unittest.TestCase):
    def test_status_identity_and_html_escaping(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);context={'plan':{'genome':'hg38','tier':'primary','callers':[]},'disable_qc':True}
            (p/'S_combined_classification_combined_top_calls.tsv').write_text('classifier_domain\tclassification_task\tsource_label\tdisplay_label\trank\tscore\n'+'blood\tcancer_classification\tMODEL\t<script>alert(1)</script>\t1\t0.1\n')
            data=ss.load('S',p,context);self.assertIsNone(data['consensus']['counts']);self.assertEqual(data['analyses']['qc'],'disabled')
            qmd=ss.render(data,ROOT/'assets/summary/template.qmd');self.assertIn('&lt;script&gt;',qmd);self.assertNotIn('<script>alert',qmd)
            self.assertLess(qmd.index('## Fusion summary'),qmd.index('## Quality control'))
            self.assertLess(qmd.index('## Fusion summary'),qmd.index('## NASVAR copy number'))
            self.assertLess(qmd.index('## Somatic consensus'),qmd.index('## Quality control'))
            (p/'metrics.json').write_text('{"sample":"OTHER"}')
            with self.assertRaises(ValueError):ss.load('S',p,context)
    def test_native_stellerator_name_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'S.tsv').write_text('gene1\tgene2\nA\tB\n')
            data=ss.load('S',p,{'plan':{'genome':'hg38','tier':'tertiary','callers':['stellerator']}})
            self.assertEqual(data['fusions']['candidates'][0]['source'],'Stellerator')
            self.assertIn('Stellerator evidence',ss.fusion_table(data))

    def test_missing_required_consensus_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):ss.load('S',d,{'plan':{'genome':'hg38','tier':'tertiary','callers':['deepsomatic','clairsto']}})
    @unittest.skipUnless(shutil.which('quarto'),'Quarto unavailable')
    def test_real_offline_render_and_empty_calls(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'S.consensus.json').write_text(json.dumps({'sample':'S','status':'completed','counts':{'snv':0,'indel':0},'queries':[],'evidence':[]}))
            data=ss.load('S',p,{'plan':{'genome':'hg38','tier':'tertiary','callers':['deepsomatic','clairsto']}})
            (p/'report.qmd').write_text(ss.render(data,ROOT/'assets/summary/template.qmd'))
            result=subprocess.run(['quarto','render',str(p/'report.qmd'),'--to','html'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if result.returncode and ('Operation not permitted' in result.stderr or 'unrecognized architecture' in result.stdout+result.stderr):
                self.skipTest('Quarto architecture probe blocked by sandbox: '+(result.stderr+result.stdout).strip())
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            text=(p/'report.html').read_text();self.assertIn('Somatic consensus',text);self.assertIn('no consensus',text.lower())
            self.assertNotRegex(text,r'<(?:script|link)[^>]+(?:src|href)="https?://')

if __name__=='__main__':unittest.main()
