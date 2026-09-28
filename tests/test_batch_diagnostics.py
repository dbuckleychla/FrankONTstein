import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('diagnostics',Path(__file__).parents[1]/'bin/aws_batch_diagnostics.py')
diag=importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

class BatchDiagnosticsTests(unittest.TestCase):
    def test_collects_without_host_access(self):
        calls=[]
        arn='arn:aws:ecs:us-west-2:123:container-instance/cluster/worker'
        def run(command, **kwargs):
            calls.append(command)
            service, operation=command[1:3]
            payload={}
            if operation=='describe-jobs':
                payload={'jobs':[{'container':{'containerInstanceArn':arn,'taskArn':'task'},'attempts':[{'container':{'containerInstanceArn':arn},'stoppedAt':1790532093448}]}]}
            elif operation=='describe-container-instances':payload={'containerInstances':[{'ec2InstanceId':'i-worker'}]}
            elif operation=='describe-instances':payload={'Reservations':[{'Instances':[{'BlockDeviceMappings':[{'Ebs':{'VolumeId':'vol-test'}}]}]}]}
            return subprocess.CompletedProcess(command,0,json.dumps(payload),'')
        args=argparse.Namespace(job_id=['job'],queue=None,profile='chosen',region='us-west-2',limit=5)
        with patch.object(diag.subprocess,'run',side_effect=run):
            report=diag.collect(args)
        self.assertEqual(len(report['workers']),1)
        self.assertEqual(len(report['workers'][0]['ebs_metrics']),7)
        self.assertEqual(report['errors'],[])
        for command in calls:
            self.assertEqual(command[command.index('--profile')+1],'chosen')
            self.assertTrue(command[2].startswith(('describe-','get-','list-')))
            self.assertNotIn('ssm',command)

    def test_preserves_api_failure(self):
        args=argparse.Namespace(job_id=['job'],queue=None,profile='chosen',region='us-west-2',limit=5)
        with patch.object(diag.subprocess,'run',return_value=subprocess.CompletedProcess([],255,'','AccessDenied')):
            report=diag.collect(args)
        self.assertEqual(len(report['errors']),2)
        self.assertEqual(report['jobs'],{})
