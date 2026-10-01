"""Release inventory must cover every selectable caller, not only today's lock entries."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImageInventoryTests(unittest.TestCase):
    def test_release_sources_cover_all_callers_and_shared_images(self):
        sources = json.loads((ROOT / 'assets/image_sources.json').read_text())
        declaration = re.search(r'static final List CALLERS = \[(.*?)\]',
                                (ROOT / 'lib/WorkflowPlan.groovy').read_text())
        self.assertIsNotNone(declaration)
        required = set(re.findall(r"'([^']+)'", declaration.group(1))) | {'preprocess', 'classy', 'summary'}
        self.assertFalse(required - sources.keys(), f'Missing image sources: {required - sources.keys()}')
        custom = {'preprocess', 'nasvar', 'summary'}
        self.assertTrue(all(sources[k] for k in required - custom))

    def test_deepsomatic_release_source_preserves_verified_pin(self):
        sources = json.loads((ROOT / 'assets/image_sources.json').read_text())
        lock = json.loads((ROOT / 'images.lock.json').read_text())
        self.assertRegex(sources['deepsomatic'], r'^google/deepsomatic@sha256:[a-f0-9]{64}$')
        self.assertEqual(sources['deepsomatic'], lock['deepsomatic'])


if __name__ == '__main__':
    unittest.main()
