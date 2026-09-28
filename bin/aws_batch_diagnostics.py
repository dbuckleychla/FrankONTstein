#!/usr/bin/env python3
"""Collect Batch/ECS/EC2/CloudWatch evidence through read-only AWS APIs, no host login."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess


def collect(args):
    results = {'collected_at': datetime.now(timezone.utc).isoformat(), 'region': args.region, 'errors': []}

    def call(service, operation, *options):
        command = ['aws', service, operation, '--profile', args.profile, '--region', args.region,
                   '--output', 'json', '--no-cli-pager', *options]
        try:
            reply = subprocess.run(command, capture_output=True, text=True, timeout=90)
            if reply.returncode:
                results['errors'].append({'api': f'{service} {operation}', 'error': reply.stderr.strip()})
                return {}
            return json.loads(reply.stdout)
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
            results['errors'].append({'api': f'{service} {operation}', 'error': str(error)})
            return {}

    ids = args.job_id or []
    if args.queue:
        summary = call('batch', 'list-jobs', '--job-queue', args.queue, '--job-status', 'FAILED', '--max-results', '100', '--no-paginate')
        results['failed_job_page'] = summary
        ids = [row['jobId'] for row in sorted(summary.get('jobSummaryList', []), key=lambda row: row.get('createdAt', 0), reverse=True)[:args.limit]]
    results['jobs'] = call('batch', 'describe-jobs', '--jobs', *ids) if ids else {}
    results['compute_environments'] = call('batch', 'describe-compute-environments')
    results['workers'] = []
    containers = {}
    for job in results['jobs'].get('jobs', []):
        for container in [job.get('container', {}), *[a.get('container', {}) for a in job.get('attempts', [])]]:
            arn = container.get('containerInstanceArn')
            if arn:
                containers.setdefault(arn, set())
                if container.get('taskArn'):
                    containers[arn].add(container['taskArn'])
    for arn, tasks in containers.items():
        parts = arn.split('/')
        worker = {'container_instance': arn}
        results['workers'].append(worker)
        if len(parts) < 3:
            worker['unavailable'] = 'Legacy short ECS ARN: cluster name cannot be inferred'
            continue
        cluster = parts[-2]
        worker['ecs_tasks'] = call('ecs', 'describe-tasks', '--cluster', cluster, '--tasks', *sorted(tasks)) if tasks else {}
        worker['ecs_instance'] = call('ecs', 'describe-container-instances', '--cluster', cluster, '--container-instances', arn)
        for instance in worker['ecs_instance'].get('containerInstances', []):
            identity = instance['ec2InstanceId']
            worker['ec2'] = call('ec2', 'describe-instances', '--instance-ids', identity)
            worker['status'] = call('ec2', 'describe-instance-status', '--instance-ids', identity, '--include-all-instances')
            worker['console'] = call('ec2', 'get-console-output', '--instance-id', identity, '--latest')
            volumes = [m['Ebs']['VolumeId'] for r in worker['ec2'].get('Reservations', []) for i in r.get('Instances', []) for m in i.get('BlockDeviceMappings', []) if 'Ebs' in m]
            worker['volumes'] = call('ec2', 'describe-volumes', '--volume-ids', *volumes) if volumes else {}
            worker['ebs_metrics'] = []
            # Query the window around observed failures, rather than only "now".
            stops = [a.get('stoppedAt', j.get('stoppedAt')) for j in results['jobs'].get('jobs', []) for a in (j.get('attempts') or [{}]) if a.get('container', j.get('container', {})).get('containerInstanceArn') == arn]
            times = [t / 1000 for t in stops if t]
            end = datetime.fromtimestamp(max(times), timezone.utc) + timedelta(minutes=10) if times else datetime.now(timezone.utc)
            start = datetime.fromtimestamp(min(times), timezone.utc) - timedelta(minutes=20) if times else end - timedelta(hours=1)
            for volume in volumes:
                for metric in ['VolumeQueueLength', 'VolumeReadOps', 'VolumeWriteOps', 'VolumeTotalReadTime', 'VolumeTotalWriteTime', 'VolumeIOPSExceededCheck', 'VolumeThroughputExceededCheck']:
                    value = call('cloudwatch', 'get-metric-statistics', '--namespace', 'AWS/EBS', '--metric-name', metric,
                                 '--dimensions', f'Name=VolumeId,Value={volume}', '--start-time', start.isoformat(), '--end-time', end.isoformat(),
                                 '--period', '60', '--statistics', 'Average', 'Maximum', 'Sum')
                    worker['ebs_metrics'].append({'volume': volume, 'metric': metric, 'data': value})
    results['note'] = 'Missing ECS/EC2/metric data may reflect resource deletion, retention or permissions; empty metrics do not establish healthy storage. No host login or infrastructure changes performed.'
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--region', required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--job-id', nargs='+')
    source.add_argument('--queue')
    parser.add_argument('--limit', type=int, default=5, choices=range(1, 101), metavar='1..100')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.job_id and len(args.job_id) > 100:
        parser.error('At most 100 job IDs per collection')
    report = collect(args)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"Saved {args.output}; {len(report['jobs'].get('jobs', []))} jobs, {len(report['workers'])} workers, {len(report['errors'])} API errors")
