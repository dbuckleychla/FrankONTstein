# AWS Batch with portable Terraform

`terraform/aws` provisions Batch CPU compute, a queue, task/instance/service IAM roles, a coordinator policy, read-only access to an existing S3 bucket, and CloudWatch logs. There are no institution-specific account IDs, AMIs, secrets or DRAGEN resources.

Credentials use the standard AWS provider chain (including `AWS_PROFILE` or assumed roles); region is explicit. Terraform state remains under your control: configure a backend appropriate for your account before production deployment. Do not commit state or real tfvars files.

```bash
cd terraform/aws
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
# Review the plan in your account before applying it.
```

The defaults create a VPC with two private compute subnets, one public NAT subnet, outbound connectivity and an S3 gateway endpoint. Alternatively, provide both `vpc_id` and `subnet_ids` for an existing network. Existing subnets must reach image registries, AWS CLI downloads and required AWS services. NAT incurs hourly/data costs even when Batch compute scales to zero; one NAT also introduces an availability-zone dependency and possible cross-zone traffic charges.

By default, Batch uses on-demand x86-64 EC2 instances with `min_vcpus=0`. Configure `instance_types`, `max_vcpus`, `scratch_gb`, and optional `spot=true`. AWS can exceed `max_vcpus` by one instance under some allocation strategies; treat it as scheduling capacity rather than a hard spending limit. The ECS-optimized AMI is selected by Batch; the launch template installs a version-pinned AWS CLI before starting ECS. Nextflow mounts the host CLI read-only into tasks, so upstream images do not each need AWS CLI installed. The coordinator still needs its own Nextflow/Java installation and AWS credentials.

Supply **`bucket_name` (required)** for an existing bucket in the deployment region.
Terraform performs a read-only bucket lookup. It never creates/deletes buckets or
changes bucket policies, encryption, versioning, public-access settings or lifecycle
rules. The bucket owner remains responsible for those settings and any cross-account
permissions. `kms_key_arn` only grants access to an existing encryption key; it does
not change the bucket's encryption configuration.

`s3_prefix` defaults to **`frankONTstein/`** (case-sensitive). Terraform outputs use
`frankONTstein/work` and `frankONTstein/results`; task/coordinator object writes and
object cleanup permissions are limited to these two paths. Bucket deletion and
bucket-setting changes are not granted. Reads remain available across the supplied
bucket and any `read_bucket_arns`; use `read_kms_key_arns` for additional encrypted
input/reference buckets. A custom nonempty `s3_prefix` can isolate deployments.

### Upgrading an existing Terraform state

Terraform 1.9 or later is required. Migration `removed` blocks with `destroy = false`
release any previously managed bucket and its settings from state **without modifying
or deleting them in AWS**. Set `bucket_name` to the existing bucket, back up your
state securely, and review/apply the upgrade plan before teardown. It should show
old S3 resources being forgotten, not destroyed. New deployments need no migration.
Do not remove these blocks while upgrading old states.

Destroying this configuration removes compute/network/IAM resources; the existing
bucket, its objects and its settings remain. Changing the prefix does not move or
delete old objects. Existing runs require their original work prefix and coordinator
cache for `-resume`; set the desired prefix before starting a new run.

`permissions_boundary_arn` supports institutional IAM boundaries without requiring them. The coordinator policy is emitted but is not attached automatically to an arbitrary user. Have your account administrator attach it to the identity that runs Nextflow. It permits task submission, job-definition registration, status/log reads, task-role passing, and scoped data access.

After an account owner applies the reviewed infrastructure:

```bash
terraform output -json nextflow_params > aws.params.json
terraform output -raw work_dir
```

Move `aws.params.json` to the workflow launch directory and launch:

```bash
nextflow run . -profile aws -params-file aws.params.json \
  -work-dir s3://YOUR_BUCKET/frankONTstein/work/RUN_ID \
  --outdir s3://YOUR_BUCKET/frankONTstein/results/RUN_ID \
  --input samples.csv --reference_bundle bundle.json \
  --targets_bed targets.bed --enrichment_bed enrichment.bed \
  --image_manifest images.lock.json --secondary
```

Use a persistent coordinator (for example, a managed server with tmux/systemd) and retain its `.nextflow` history/cache. Losing the launcher's state can prevent resume even when S3 work objects survive. On interruption, rerun with `-resume`, the same launch directory and work prefix. Spot interruptions use Nextflow's bounded retry behavior; deterministic application errors terminate instead of retrying indefinitely.

No live AWS resources were created during implementation. Before claiming this backend validated, run the real primary fixture, a secondary/tertiary fixture, an interrupted/resumed run, and both managed-network and existing-network plans in an actual test account.

For optional Clair3 GPU execution, set `gpu_instance_types = ["g5"]` to create a separate NVIDIA Batch environment/queue, then launch with `--clair3_gpu`. CPU-only remains the default. GPU resources scale to zero and use on-demand capacity independently of the CPU Spot setting. The chosen Clair3 image must include compatible GPU dependencies; this path requires its own hardware validation.

Offline storage contract tests use the mocked AWS provider: `terraform test`
from `terraform/aws` (no AWS deployment). They cover the default/custom prefixes
and reject root/parent prefixes and bucket URLs.
