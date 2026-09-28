import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('namer', Path(__file__).parents[1]/'bin/name_sample_artifacts.py')
namer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(namer)

class OutputNamingTests(unittest.TestCase):
    def test_links_indexes_and_binary_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'artifacts'
            (root/'classy/plots').mkdir(parents=True)
            (root/'classy/index.html').write_text('<a href="plots/plot.png">plot</a><a href="BC3.existing.json">json</a>')
            (root/'classy/BC3.existing.json').write_text('{"plot":"classy/plots/plot.png"}')
            (root/'classy/plots/plot.png').write_bytes(b'\x00\xff')
            (root/'delly.bcf').write_bytes(b'BCFbinary')
            (root/'delly.bcf.csi').write_bytes(b'index')
            namer.rename_artifacts(root, 'BC3')
            self.assertTrue(all('BC3' in p.name for p in root.rglob('*') if p.is_file()))
            self.assertIn('plots/BC3.plot.png', (root/'classy/BC3.index.html').read_text())
            self.assertIn('classy/plots/BC3.plot.png', (root/'classy/BC3.existing.json').read_text())
            self.assertEqual((root/'BC3.delly.bcf').read_bytes(), b'BCFbinary')
            self.assertTrue((root/'BC3.delly.bcf.csi').exists())
            namer.rename_artifacts(root, 'BC3') # idempotent

    def test_collision_rejected_before_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'report.txt').write_text('one')
            (root/'BC3.report.txt').write_text('two')
            with self.assertRaises(ValueError):
                namer.rename_artifacts(root, 'BC3')
            self.assertEqual((root/'report.txt').read_text(), 'one')
