import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('aws_batch_env', ROOT / 'bin/aws_batch_env.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def outputs(gpu='gpu-queue'):
    return {'nextflow_params': {'value': {
        'aws_region': 'us-west-2', 'aws_queue': 'cpu-queue', 'aws_gpu_queue': gpu,
        'aws_job_role': 'arn:aws:iam::123456789012:role/test-task',
        'aws_logs_group': '/test/batch', 'aws_cli_path': '/opt/aws-cli/v2/current/bin/aws',
        'outdir': 's3://test-bucket/project/results/'}},
        'work_dir': {'value': 's3://test-bucket/project/work/'}}


class AWSEnvironmentTests(unittest.TestCase):
    def test_resolves_outputs_and_run_paths(self):
        result = helper.build_environment(outputs(), 'run_1h')
        self.assertEqual(result['FRANKONTSTEIN_AWS_GPU_QUEUE'], 'gpu-queue')
        self.assertEqual(result['FRANKONTSTEIN_OUTDIR'], 's3://test-bucket/project/results/run_1h')
        self.assertEqual(result['FRANKONTSTEIN_WORK_DIR'], 's3://test-bucket/project/work/run_1h')
        self.assertNotIn('AWS_PROFILE', result)
        self.assertEqual(len(result), 8)

    def test_cpu_only_outputs_clear_previous_gpu_queue(self):
        self.assertEqual(helper.build_environment(outputs(None), 'run1')['FRANKONTSTEIN_AWS_GPU_QUEUE'], '')

    def test_invalid_or_incomplete_outputs(self):
        for data in [[], {}, {'nextflow_params': {'value': {}}},
                     outputs() | {'work_dir': {'value': '/local/work'}}]:
            with self.assertRaises(ValueError):
                helper.build_environment(data, 'run1')
        for run_id in ['../run', 'run/path', 'run name', '']:
            with self.assertRaises(ValueError):
                helper.build_environment(outputs(), run_id)

    def test_terraform_invocation_is_output_only_and_inherits_environment(self):
        with patch.object(helper.subprocess, 'run') as run:
            run.return_value.stdout = json.dumps(outputs())
            self.assertEqual(helper.read_outputs(Path('/terraform path')), outputs())
            self.assertEqual(run.call_args.args[0], ['terraform', '-chdir=/terraform path', 'output', '-json'])
            self.assertNotIn('env', run.call_args.kwargs)

    def test_saved_outputs_do_not_require_terraform(self):
        with tempfile.TemporaryDirectory() as temp:
            export = Path(temp) / 'outputs.json'
            export.write_text(json.dumps(outputs()))
            with patch.object(helper.subprocess, 'run') as run:
                self.assertEqual(helper.read_outputs(None, export), outputs())
                run.assert_not_called()
            result = subprocess.run([sys.executable, str(ROOT / 'bin/aws_batch_env.py'),
                                     '--terraform-outputs', str(export), '--run-id', 'run1'],
                                    check=True, text=True, capture_output=True)
            self.assertEqual(result.stdout, helper.shell_exports(helper.build_environment(outputs(), 'run1')))

    def test_exports_roundtrip_without_executing_shell_characters(self):
        with tempfile.TemporaryDirectory() as temp:
            sentinel = Path(temp) / 'must-not-exist'
            data = outputs()
            data['nextflow_params']['value']['aws_queue'] = f"queue ' $(touch {sentinel}) `touch {sentinel}` ; end"
            expected = helper.build_environment(data, 'run1')
            script = Path(temp) / 'exports.sh'
            script.write_text(helper.shell_exports(expected))
            result = subprocess.run(['/bin/bash', '-c', '. "$1"; "$2" -c \'import os,json; print(json.dumps({k:v for k,v in os.environ.items() if k.startswith("FRANKONTSTEIN_")}))\'',
                                     'test', str(script), sys.executable],
                                    check=True, text=True, capture_output=True,
                                    env={k:v for k,v in os.environ.items() if not k.startswith('FRANKONTSTEIN_')})
            self.assertEqual(json.loads(result.stdout), expected)
            self.assertFalse(sentinel.exists())

    def test_output_failure_emits_no_shell_code(self):
        result = subprocess.run([sys.executable, str(ROOT / 'bin/aws_batch_env.py'),
                                 '--run-id', 'run1', '--terraform-outputs', '/nonexistent/outputs.json'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
