# AWS Batch with portable Terraform

`terraform/aws` provisions Batch CPU compute, a queue, task/instance/service IAM roles, a coordinator policy, encrypted storage when requested, and CloudWatch logs. There are no institution-specific account IDs, AMIs, secrets or DRAGEN resources.

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

Supply `bucket_name` to reuse a bucket, otherwise Terraform creates an account/region-qualified bucket with versioning, encryption, TLS-only policy, and public access blocked. Tasks can write only `work/` and `results/` and read configured input/reference buckets. Add `read_bucket_arns` and `read_kms_key_arns` as needed. A managed bucket has `prevent_destroy=true`: a normal destroy is intentionally blocked while the bucket remains in state. To remove compute while retaining data, use a reviewed state/configuration separation procedure; do not disable protection casually.

`permissions_boundary_arn` supports institutional IAM boundaries without requiring them. The coordinator policy is emitted but is not attached automatically to an arbitrary user. Have your account administrator attach it to the identity that runs Nextflow. It permits task submission, job-definition registration, status/log reads, task-role passing, and scoped data access.

After an account owner applies the reviewed infrastructure:

```bash
terraform output -json nextflow_params > aws.params.json
terraform output -raw work_dir
```

Move `aws.params.json` to the workflow launch directory and launch:

```bash
nextflow run . -profile aws -params-file aws.params.json \
  -work-dir s3://YOUR_BUCKET/work/RUN_ID \
  --outdir s3://YOUR_BUCKET/results/RUN_ID \
  --input samples.csv --reference_bundle bundle.json \
  --targets_bed targets.bed --enrichment_bed enrichment.bed \
  --image_manifest images.lock.json --secondary
```

Use a persistent coordinator (for example, a managed server with tmux/systemd) and retain its `.nextflow` history/cache. Losing the launcher's state can prevent resume even when S3 work objects survive. On interruption, rerun with `-resume`, the same launch directory and work prefix. Spot interruptions use Nextflow's bounded retry behavior; deterministic application errors terminate instead of retrying indefinitely.

No live AWS resources were created during implementation. Before claiming this backend validated, run the real primary fixture, a secondary/tertiary fixture, an interrupted/resumed run, and both managed-network and existing-network plans in an actual test account.

For optional Clair3 GPU execution, set `gpu_instance_types = ["g5"]` to create a separate NVIDIA Batch environment/queue, then launch with `--clair3_gpu`. CPU-only remains the default. GPU resources scale to zero and use on-demand capacity independently of the CPU Spot setting. The chosen Clair3 image must include compatible GPU dependencies; this path requires its own hardware validation.
