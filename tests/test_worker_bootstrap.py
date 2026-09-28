import email
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('terraform'), 'Terraform is needed to render the actual bootstrap template')
class WorkerBootstrapTests(unittest.TestCase):
    def test_rendered_bootstrap_and_log_configuration(self):
        source=(ROOT/'terraform/aws/observability.tf').read_text()
        config=source[source.index('locals {'):source.index('\noutput "host_diagnostics"')]
        config=config.replace('var.region','"us-west-2"').replace('aws_cloudwatch_log_group.hosts.name','"/test/hosts"')
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'main.tf').write_text(config)
            for existing in (True,False):
                expression='jsonencode(templatefile('+json.dumps(str(ROOT/'terraform/aws/templates/user_data.mime'))+', {aws_cli_version="2.31.0", use_existing_aws_cli='+str(existing).lower()+', existing_aws_cli_path="/opt/aws/bin/aws", host_agent_config=local.host_agent_config}))\n'
                result=subprocess.run(['terraform','console'],cwd=directory,input=expression,text=True,capture_output=True,check=True,timeout=30)
                mime=result.stdout.strip()
                for _ in range(4):
                    if mime.startswith('MIME-Version:'):break
                    mime=json.loads(mime)
                self.assertLess(len(mime.encode()),16384)
                payload=email.message_from_string(mime).get_payload()[0].get_payload(decode=True)
                subprocess.run(['bash','-n'],input=payload,check=True,timeout=10)
                script=payload.decode()
                self.assertLess(script.index('amazon-cloudwatch-agent-ctl'),script.index('systemctl start ecs --no-block'))
                self.assertIn('ECS_IMAGE_PULL_BEHAVIOR=once',script)
                self.assertEqual('awscli.amazonaws.com' in script,not existing)
                agent=json.loads(script.split("<<'CONFIG'\n",1)[1].split('\nCONFIG',1)[0])
                self.assertEqual(agent['metrics']['append_dimensions']['InstanceId'],'${aws:InstanceId}')
                entries=agent['logs']['logs_collected']['files']['collect_list']
                self.assertEqual(len(entries),4)
                self.assertTrue(all(entry['log_group_name']=='/test/hosts' for entry in entries))
                self.assertIn('/var/log/frankontstein/host-journal.log',[entry['file_path'] for entry in entries])
