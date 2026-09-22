import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'bin' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

reference = load('check_reference')
nasvar = load('run_nasvar')
report = load('make_report')

class ReferenceTests(unittest.TestCase):
    def test_gff_tabs_preserve_spaces_and_aliases(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'genes.gff3'
            config = Path(d) / 'reference.json'
            config.write_text(json.dumps({'contigs':[{'name':'chr1','accession':'NC_000001.11'}]}))
            aliases = reference.contig_aliases(config, {'chr1':100})
            text = ('##gff-version 3\nNC_000001.11\tBest RefSeq\tpseudogene\t1\t100\t.\t+\t.\t'
                    'ID=gene-A;Name=A;description=some gene\n##FASTA\n>NC_000001.11\nACGT\n')
            path.write_text(text)
            reference.coordinates(path, {'chr1':100}, 'gff', aliases)
            self.assertEqual(path.read_text(), text)
            with self.assertRaisesRegex(ValueError, 'no coordinate records overlap'):
                reference.coordinates(path, {'chr1':100}, 'gff')
            path.write_text(text.replace('\t100\t', '\t101\t'))
            with self.assertRaisesRegex(ValueError, 'exceeds'):
                reference.coordinates(path, {'chr1':100}, 'gff', aliases)

    def test_gff_malformed_columns_report_line(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'genes.gff3'
            path.write_text('##gff-version 3\nchr1 source gene 1 10 . + . ID=a\n')
            with self.assertRaisesRegex(ValueError, 'genes.gff3:2: GFF3 requires 9 tab-separated'):
                reference.coordinates(path, {'chr1':100}, 'gff')
            path.write_text('chr1\tsource\tgene\tpseudogene\t10\t.\t+\t.\tID=a\n')
            with self.assertRaisesRegex(ValueError, 'genes.gff3:1: invalid gff coordinate'):
                reference.coordinates(path, {'chr1':100}, 'gff')

    def test_reference_alias_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            config = Path(d) / 'reference.json'
            config.write_text(json.dumps({'contigs':[{'name':'chr1','accession':'NC_000001.11'}]}))
            with self.assertRaisesRegex(ValueError, 'conflicting FASTA lengths'):
                reference.contig_aliases(config, {'chr1':100,'NC_000001.11':101})

    def test_primary_contigs_required(self):
        lengths = dict.fromkeys(reference.PRIMARY_CONTIGS, 100)
        reference.primary_contigs(lengths)
        del lengths['chrY']
        with self.assertRaisesRegex(ValueError, 'chrY'):
            reference.primary_contigs(lengths)

    def test_extra_annotation_contigs_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.bed'
            text = 'chr1\t0\t10\nchrUn_extra\t0\t20\n'
            path.write_text(text)
            reference.coordinates(path, {'chr1': 10})
            self.assertEqual(path.read_text(), text)
            path.write_text('chr1\t0\t11\nchrUn_extra\t0\t20\n')
            with self.assertRaises(ValueError):
                reference.coordinates(path, {'chr1': 10})

    def test_coordinates_and_mismatches(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.bed'
            path.write_text('chr1\t0\t10\n')
            reference.coordinates(path, {'chr1': 10})
            for line in ['1\t0\t10', 'chr1\t-1\t10', 'chr1\t0\t11', 'chr1\t5\t5', '']:
                path.write_text(line)
                with self.assertRaises(ValueError):
                    reference.coordinates(path, {'chr1': 10})

class NasvarTests(unittest.TestCase):
    def test_error_with_zero_exit_is_failure(self):
        with tempfile.TemporaryDirectory() as d:
            result = subprocess.CompletedProcess([], 0, 'ERROR failed to open reference')
            with patch.object(nasvar.subprocess, 'run', return_value=result):
                with self.assertRaises(RuntimeError): nasvar.execute(['coverage'], Path(d) / 'log')

    def test_secondary_preserves_overwritten_sections_and_purity(self):
        calls = []
        def fake(args, log):
            calls.append(args)
            if args[0] == '--version': return
            prefix = args[args.index('--out-prefix') + 1]
            if args[0] in ['coverage', 'maf']:
                suffix = '.coverage.tsv' if args[0] == 'coverage' else '.maf'
                Path(prefix + suffix).write_text('data')
            if args[0] in ['cnv', 'fusions', 'karyotype']:
                if args[0] == 'cnv':
                    # The pinned CLI reads previous karyotype before overwriting JSON.
                    self.assertIn('karyotype', json.loads(Path(prefix + '.result.json').read_text()))
                    self.assertEqual(args[args.index('--blast-ratio') + 1], '0.4')
                section = {'blast_ratio': .4} if args[0] == 'karyotype' else {}
                Path(prefix + '.result.json').write_text(json.dumps({args[0]:section}))
            if args[0] == 'report': Path(prefix + '.report.html').write_text('<html/>')
        with tempfile.TemporaryDirectory() as d:
            old = os.getcwd()
            try:
                os.chdir(d)
                a = types.SimpleNamespace(**{k:k for k in ['sample','bam','fasta','repeats','enriched','sites','targets','gff','config','reference']}, tier='secondary')
                with patch.object(nasvar, 'execute', side_effect=fake): nasvar.run(a)
                output = json.loads(Path('nasvar/sample.result.json').read_text())
                self.assertEqual(set(output), {'karyotype', 'cnv', 'fusions'})
                self.assertEqual([c[0] for c in calls], ['coverage','maf','karyotype','cnv','fusions','breakpoints','report','--version'])
            finally: os.chdir(old)

    def test_tertiary_runs_pipeline_once(self):
        calls = []
        def fake(args, log):
            calls.append(args[0])
            if args[0] == 'pipeline':
                Path('nasvar/sample.result.json').write_text(json.dumps({k:{} for k in ['cnv','karyotype','fusions','snv','itd']}))
            if args[0] == 'report': Path('nasvar/sample.report.html').write_text('<html/>')
        with tempfile.TemporaryDirectory() as d:
            old = os.getcwd()
            try:
                os.chdir(d)
                a = types.SimpleNamespace(**{k:k for k in ['sample','bam','fasta','repeats','enriched','sites','targets','gff','config','reference']}, tier='tertiary')
                with patch.object(nasvar, 'execute', side_effect=fake): nasvar.run(a)
                self.assertEqual(calls, ['pipeline','report','--version'])
            finally: os.chdir(old)

class ReportTests(unittest.TestCase):
    def test_escape_labels_and_links(self):
        text = report.render({'analyses':[{'sample':'<script>', 'analysis':'a', 'status':'completed', 'files':['s/a&b.html']}]})
        self.assertNotIn('<script>',text)
        self.assertIn('&lt;script&gt;',text)
        self.assertIn('s/a%26b.html',text)

if __name__ == '__main__': unittest.main()
