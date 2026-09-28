import importlib.util
from pathlib import Path
import unittest
import tempfile
import subprocess
import os
import sys
import gzip

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ds', ROOT / 'bin/run_deepsomatic_task.py')
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)

class DeepSomaticTests(unittest.TestCase):
    def test_ont_tumor_only_command(self):
        command = ds.build_command('/bin/run_deepsomatic', 'tumor.bam', 'ref.fa', 'targets.bed', 'BC3', 8)
        self.assertIn('--model_type=ONT_TUMOR_ONLY', command)
        self.assertIn('--sample_name_tumor=BC3', command)
        self.assertIn('--num_shards=8', command)
        self.assertIn('--use_default_pon_filtering=true', command)
        self.assertIn('--dry_run=false', command)
        self.assertIn('--regions=' + str(Path('targets.bed').resolve()), command)
        self.assertFalse(any('reads_normal' in flag for flag in command))
        self.assertFalse(any('enrichment' in flag for flag in command))

    def test_cpu_hides_gpu(self):
        self.assertEqual(ds.gpu_environment(False)['CUDA_VISIBLE_DEVICES'], '-1')

    def run_fake(self, root, exit_code=0, emit_index=True):
        executable = root / 'run_deepsomatic'
        executable.write_text('#!' + sys.executable + '\n' +
            'import sys, pathlib, gzip\n' +
            'if \"--version\" in sys.argv: print(\"DeepSomatic: DeepVariant version 1.10.0\"); sys.exit(0)\n' +
            'print("DeepSomatic test progress", flush=True)\n' +
            f'code = {exit_code}\n' +
            'if code: sys.exit(code)\n' +
            'output = pathlib.Path(next(a.split("=",1)[1] for a in sys.argv if a.startswith("--output_vcf=")))\n' +
            'with gzip.open(output, "wt") as handle: handle.write("##fileformat=VCFv4.2\\n#CHROM\\tPOS\\tID\\tREF\\tALT\\tQUAL\\tFILTER\\tINFO\\n")\n' +
            ("pathlib.Path(str(output) + '.tbi').write_bytes(b'index fixture')\n" if emit_index else ''))
        executable.chmod(0o755)
        (root / 'targets.bed').write_text('chr1\t10\t20\n')
        env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'])
        return subprocess.run([sys.executable, '-c',
            f'import runpy; m=runpy.run_path({str(ROOT / "bin/run_deepsomatic_task.py")!r}); m["main"].__globals__["bundled_assets"]=lambda: {{}}; m["main"]()',
            '--bam','sample.bam','--ref','ref.fa','--targets','targets.bed',
            '--sample','BC3','--cpus','1','--image','test-image'],
            cwd=root,env=env,text=True,capture_output=True)

    def test_failure_is_propagated_and_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_fake(root, exit_code=17)
            self.assertEqual(result.returncode, 17)
            self.assertIn('test progress', (root / 'results/logs/runner.log').read_text())

    def test_empty_vcf_is_allowed_and_index_required(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_fake(Path(directory))
            self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_fake(Path(directory), emit_index=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('somatic.vcf.gz.tbi', result.stderr)

    def test_missing_bundled_model_fails_without_download(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'missing bundled asset'):
                ds.bundled_assets(directory)

    def test_bundled_model_and_pon_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('ont_tumor_only/saved_model.pb',
                         'ont_tumor_only/model.example_info.json',
                         'ont_tumor_only/variables/variables.index',
                         'ont_tumor_only/variables/variables.data-00000-of-00001',
                         'pons/' + ds.PON_NAME, 'pons/' + ds.PON_NAME + '.tbi'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
            self.assertEqual(len(ds.bundled_assets(root)), 6)
            self.assertTrue(all(len(value) == 64 for value in ds.bundled_assets(root).values()))

    def test_invalid_shards(self):
        with self.assertRaises(ValueError):
            ds.build_command('run', 'bam', 'ref', 'bed', 'sample', 0)

if __name__ == '__main__':
    unittest.main()
