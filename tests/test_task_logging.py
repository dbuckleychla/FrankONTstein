import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class TaskLoggingTests(unittest.TestCase):
    def run_task(self, command):
        with tempfile.TemporaryDirectory() as directory:
            env=dict(os.environ, PATH=str(ROOT/'bin')+os.pathsep+os.environ['PATH'])
            result=subprocess.run(['bash','-euo','pipefail','-c',
                'source capture_task_logs.sh TEST\n'+command], cwd=directory, env=env,
                capture_output=True, timeout=20)
            logs=Path(directory)/'runtime_logs/TEST'
            return result, (logs/'stdout.log').read_bytes(), (logs/'stderr.log').read_bytes()

    def test_streams_and_drains_before_exit(self):
        result, out, err=self.run_task("head -c 1048576 /dev/zero; printf diagnostic >&2")
        self.assertEqual(result.returncode,0)
        self.assertEqual(len(out),1048576)
        self.assertEqual(out,result.stdout)
        self.assertEqual(err,b'diagnostic')
        self.assertEqual(err,result.stderr)

    def test_failure_exit_preserved(self):
        result, out, err=self.run_task('echo started; echo failed >&2; exit 23')
        self.assertEqual(result.returncode,23)
        self.assertEqual(out,b'started\n')
        self.assertEqual(err,b'failed\n')

    def test_pipefail_preserved(self):
        result, out, err=self.run_task('false | cat\necho should-not-run')
        self.assertEqual(result.returncode,1)
        self.assertEqual(out,b'')

    def test_empty_logs_exist(self):
        result, out, err=self.run_task('true')
        self.assertEqual(result.returncode,0)
        self.assertEqual((out,err),(b'',b''))
