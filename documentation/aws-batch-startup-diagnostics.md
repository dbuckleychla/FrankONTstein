# Batch container startup failures without host login

`DockerTimeoutError: Could not transition to created` occurs before the task
script starts. CPU/RAM requests and successful application retries do not
establish why Docker timed out. Host disk pressure, daemon delays and image
preparation need evidence. Raising the startup timeout is not a diagnosis.

## Workflow concurrency

No additional concurrency cap is imposed on trim, demux, prepare or publish.
Existing executor/resource limits and the independently configured basecalling
limit still apply. Keep the original explicit session ID when resuming; bare
`-resume` can select a newer validation/test session in the same launch directory.

## Collect evidence now

Run on the coordinator or your workstation, using your chosen AWS profile:

```bash
python3 bin/aws_batch_diagnostics.py \
  --profile YOUR_PROFILE --region us-west-2 \
  --queue YOUR_CPU_QUEUE --limit 5 \
  --output /tmp/batch-diagnostics.json
```

For specific failures, replace `--queue ... --limit ...` with
`--job-id JOB_ID_1 JOB_ID_2`. The helper only calls read-only AWS APIs; it neither
logs into hosts nor submits jobs. It captures job reasons, ECS task/worker details,
EC2 console/status/storage information, and EBS metrics around the failure times.
For queue mode it samples up to 100 entries from one FAILED-jobs page, then selects
up to the requested limit; use explicit IDs when the desired jobs are not present.
Per-API errors are retained so AccessDenied or deleted resources aren't mistaken
for healthy systems. Keep reports private: they contain infrastructure and job
metadata. ECS stopped tasks and terminated workers may already be unavailable.

Required reader actions: batch:ListJobs, batch:DescribeJobs,
batch:DescribeComputeEnvironments, ecs:DescribeTasks,
ecs:DescribeContainerInstances, ec2:DescribeInstances,
ec2:DescribeInstanceStatus, ec2:GetConsoleOutput, ec2:DescribeVolumes, and
cloudwatch:GetMetricStatistics. Host-log readers additionally need
logs:DescribeLogStreams, logs:GetLogEvents and logs:FilterLogEvents.

## Prepared worker changes (requires reviewed Terraform deployment)

Both CPU and GPU environments share the launch template. New workers:

- Reuse locally cached digest-pinned images with ECS_IMAGE_PULL_BEHAVIOR=once;
  missing images still require a registry download.
- Provision root gp3 storage at configurable `scratch_iops = 6000` and
  `scratch_throughput_mibps = 500` (previous implicit defaults: 3000 / 125).
  This disk serves both Docker and task scratch. Instance EBS bandwidth can cap
  actual performance. Above-baseline gp3 performance incurs additional charges;
  set 3000 / 125 explicitly to retain baseline performance/cost.
- Forward the system journal (including Docker/kernel messages), ECS agent logs,
  bootstrap output, and logging-agent errors to `/<stack-name>/hosts`, with
  instance-ID stream prefixes and configured log retention. The journal export
  rotates locally so it does not grow without bound.
- Publish memory, swap, root disk usage/inodes and disk I/O metrics every minute
  in `FrankONTstein/BatchHost`, dimensioned by InstanceId. Custom metrics/log
  ingestion also have cost. Logs normally flush every five seconds; abrupt
  termination can lose the last buffered events.

No SSH, SSM agent registration, public IP, or inbound port is required. Worker
instance-role permissions are scoped to the host log group and metrics namespace.
Private subnets still need outbound access: NAT or suitable endpoints for
CloudWatch Logs (`logs`) and CloudWatch metrics (`monitoring`), plus package/image
sources. GHCR requires outbound internet access. Existing permissions boundaries
must allow the new worker actions. The coordinator identity applying Terraform
also needs iam:PutRolePolicy/GetRolePolicy/DeleteRolePolicy for the worker inline
policy, and CloudWatch log-group lifecycle permissions. No account-wide SSM
Default Host Management configuration is introduced.

The bootstrap installs amazon-cloudwatch-agent and logrotate from AL2023 package
repositories even with use_existing_aws_cli=true. Logging setup must succeed
before ECS starts accepting jobs. Review networking/package availability first.

Validate and review, without deployment:

```bash
terraform -chdir=terraform/aws fmt -check -recursive
terraform -chdir=terraform/aws validate
terraform -chdir=terraform/aws test
terraform -chdir=terraform/aws plan
```

Review the plan before applying: compute-environment updates can rotate workers.
Schedule rollout between runs; do not interrupt running analyses or manually
terminate workers as part of diagnosis. Existing workers do not receive modified
user data or disk settings retroactively. 

After deployment, `terraform -chdir=terraform/aws output host_diagnostics` shows
log/metric locations. Confirm a fresh worker has bootstrap and journal streams
before launching a full run. If startup times out again, correlate Docker/ECS
messages with disk I/O, memory, free space and the worker ID. Empty metrics or a
missing stream require investigation of logging/IAM/connectivity; they do not
prove the host was healthy. These changes are mitigations and evidence collection,
not proof that storage caused the original failures.
