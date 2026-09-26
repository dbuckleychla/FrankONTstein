import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('models', ROOT / 'bin/check_basecall_models.py')
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)


class ModelTests(unittest.TestCase):
    def assets(self, root, version='5.0.0', mode='sup'):
        base = Path(root) / f'dna_r10.4.1_e8.2_400bps_{mode}@v{version}'
        mod = Path(root) / (base.name + '_5mCG_5hmCG@v2')
        for path in [base, mod]:
            path.mkdir()
            (path / 'config.toml').write_text('[model]\n')
            (path / 'weights.tensor').write_bytes(b'fixture weights')
        return base, mod

    def test_pair_and_content_checksum(self):
        with tempfile.TemporaryDirectory() as root:
            base, mod = self.assets(root)
            first = models.validate(base, mod, 'sup')
            self.assertEqual(first, models.validate(base, mod, 'sup'))
            (base / 'weights.tensor').write_bytes(b'changed weights')
            self.assertNotEqual(first['model']['sha256'], models.validate(base, mod)['model']['sha256'])
            self.assertEqual(first['modified_model'], models.validate(base, mod)['modified_model'])

    def test_missing_weights(self):
        with tempfile.TemporaryDirectory() as root:
            base, mod = self.assets(root)
            (mod / 'weights.tensor').unlink()
            with self.assertRaisesRegex(ValueError, 'tensor'):
                models.validate(base, mod)

    def test_wrong_modification_model(self):
        with tempfile.TemporaryDirectory() as root:
            base, mod = self.assets(root)
            renamed = mod.with_name(base.name + '_5mCG@v2')
            mod.rename(renamed)
            with self.assertRaisesRegex(ValueError, 'combined'):
                models.validate(base, renamed)

    def test_external_clair3_weights_and_matching(self):
        for mode in ('sup', 'hac'):
            with tempfile.TemporaryDirectory() as root:
                base, mod = self.assets(root, '5.2.0', mode)
                external = Path(root) / f'r1041_e82_400bps_{mode}_v520_with_mv'
                external.mkdir()
                for name in ('pileup.pt', 'full_alignment.pt'):
                    (external / name).write_bytes(b'weights')
                result = models.validate(base, mod, mode, external)
                self.assertTrue(result['clair3_model']['requires_moves'])
                with self.assertRaisesRegex(ValueError, 'match Dorado'):
                    models.validate(base, mod, 'hac' if mode == 'sup' else 'sup', external)
                (external / 'pileup.pt').unlink()
                with self.assertRaisesRegex(ValueError, 'pileup.pt'):
                    models.validate(base, mod, mode, external)

    def test_clair3_version_and_accuracy(self):
        with tempfile.TemporaryDirectory() as root:
            base, mod = self.assets(root, '5.2.0')
            models.validate(base, mod)
            with self.assertRaisesRegex(ValueError, 'Clair3'):
                models.validate(base, mod, 'sup')
        with tempfile.TemporaryDirectory() as root:
            base, mod = self.assets(root)
            with self.assertRaisesRegex(ValueError, 'Clair3'):
                models.validate(base, mod, 'hac')


if __name__ == '__main__':
    unittest.main()
