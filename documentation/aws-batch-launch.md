# Load AWS Batch settings from Terraform

[`bin/aws_batch_env.py`](../bin/aws_batch_env.py) reads Terraform outputs and emits
shell environment exports. It does not run Nextflow or apply Terraform. It needs
Python 3.8+ and Terraform; no `jq`, PyYAML or additional Python packages are needed.

A helper process cannot modify its parent shell's environment. Load its output
into your current bash/zsh session, then use your normal `nextflow run` command:

```bash
AWS_BATCH_ENV="$(python3 bin/aws_batch_env.py --run-id run1)" &&
  eval "$AWS_BATCH_ENV"

nextflow run . -profile aws \
  -params-file assets/aws_batch_references.yaml \
  --primary --bam s3://YOUR_INPUT_BUCKET/run1/sample.bam \
  --sample_id sample1 --genome hg38
```

Check that loading succeeds before starting Nextflow. The helper validates all
outputs before printing shell-quoted exports and exits nonzero on errors. An
unsuccessful load leaves any previously loaded environment in your shell intact.
Your AWS credentials and `AWS_PROFILE` are inherited unchanged.

For multiplexed POD5, use a separate run label for the output/work directories
and the sequencer sheet's `experiment_id` for `--sample_id`:

```bash
AWS_BATCH_ENV="$(python3 bin/aws_batch_env.py --run-id experiment1_1h)" &&
  eval "$AWS_BATCH_ENV"

nextflow run . -profile aws \
  -params-file assets/aws_batch_references.yaml \
  --primary --basecall --pod5 s3://YOUR_INPUT_BUCKET/experiment1/first_hour/ \
  --sample_id experiment1 --genome hg38 \
  --demux_samplesheet experiment1.csv
```

`--demux_samplesheet` accepts a local path or an S3 URI:

```bash
--demux_samplesheet ONT20260917.csv
# Or, after placing the sheet in S3:
--demux_samplesheet s3://YOUR_INPUT_BUCKET/experiment1/ONT20260917.csv
```

Relative local paths resolve from the directory where you launch Nextflow.
Nextflow reads the CSV on the coordinator before scheduling demultiplexing, so a
local sheet does not need to be uploaded for AWS Batch. For an S3 sheet, the
coordinator's AWS credentials must allow reading that object.

The YAML still supplies reference files, both BEDs, the image lock and Dorado
model directories. The helper does not change the current directory or input,
sample-sheet and reference-path resolution.

## Exported defaults

Only the `aws` Nextflow profile reads these variables. Other profiles are not
affected. CLI parameters and parameters-file values retain their normal priority
over environment-derived defaults; `-work-dir` overrides the environment work
path. You can inspect the helper's output by running it without `eval`.

| Terraform output | Environment variable | Nextflow setting |
| --- | --- | --- |
| `nextflow_params.aws_region` | `FRANKONTSTEIN_AWS_REGION` | `params.aws_region` |
| `nextflow_params.aws_queue` | `FRANKONTSTEIN_AWS_QUEUE` | `params.aws_queue` |
| `nextflow_params.aws_gpu_queue` | `FRANKONTSTEIN_AWS_GPU_QUEUE` | `params.aws_gpu_queue` |
| `nextflow_params.aws_job_role` | `FRANKONTSTEIN_AWS_JOB_ROLE` | `params.aws_job_role` |
| `nextflow_params.aws_logs_group` | `FRANKONTSTEIN_AWS_LOGS_GROUP` | `params.aws_logs_group` |
| `nextflow_params.aws_cli_path` | `FRANKONTSTEIN_AWS_CLI_PATH` | `params.aws_cli_path` |
| `nextflow_params.outdir` + run ID | `FRANKONTSTEIN_OUTDIR` | `params.outdir` |
| `work_dir` + run ID | `FRANKONTSTEIN_WORK_DIR` | `workDir` |

Missing optional outputs are exported as empty strings so switching to a stack
without a GPU queue does not retain a previously exported GPU queue. The workflow
still rejects basecalling when no GPU queue is configured. The helper does not
export or change AWS credentials, `AWS_PROFILE`, tier flags or resource limits.

It reads actual outputs, not tfvars: tfvars cannot supply generated role ARNs
and do not establish which resources were successfully deployed. `instance_types`,
`max_vcpus`, GPU instance families, networking and boundaries remain infrastructure
settings. They are not translated into per-task Nextflow CPU/memory limits.

## Alternate Terraform directories and saved exports

The default Terraform directory is the checkout's `terraform/aws`. Use
`--terraform-dir /path/to/terraform` to select another initialized directory.
Terraform reads that directory's backend/state and selected workspace; environment
settings such as `AWS_PROFILE` and `TF_WORKSPACE` are inherited. The helper never
runs init, plan, apply or destroy and does not select an account/workspace.

To use it on a coordinator without Terraform or backend access, save the full
output document on the deployment host:

```bash
mkdir -p .aws-batch
terraform -chdir=terraform/aws output -json > .aws-batch/terraform-outputs.json
```

Transfer the export to the coordinator and load it:

```bash
AWS_BATCH_ENV="$(python3 bin/aws_batch_env.py \
  --terraform-outputs .aws-batch/terraform-outputs.json \
  --run-id run1)" && eval "$AWS_BATCH_ENV"
```

The file must contain both `nextflow_params` and `work_dir` in the full
`terraform output -json` format. An export of only `nextflow_params` is insufficient.
Keep deployment metadata out of version control; `.aws-batch/` is ignored.
Refresh saved exports after infrastructure changes. No live credentials or
permissions are verified by reading a saved export.

Alternatively, generate a shell file and source it:

```bash
mkdir -p .aws-batch
python3 bin/aws_batch_env.py --run-id run1 > .aws-batch/run1.env.sh &&
  source .aws-batch/run1.env.sh
```

To resume, retain the same run ID, output/work prefixes, coordinator launch
directory and Nextflow cache, then add `-resume` to `nextflow run`. Run IDs must
start with a letter/digit and contain only letters, digits, dots, underscores
or hyphens; directory separators are rejected.

## Reuse AWS CLI from the EC2 AMI

Terraform normally installs the pinned AWS CLI during instance bootstrap. To use
an existing installation, set these in `terraform/aws/terraform.tfvars`:

```hcl
use_existing_aws_cli  = true
existing_aws_cli_path = "/usr/local/aws-cli/v2/current/bin/aws"
```

Set the path to the actual self-contained CLI installation in your CPU and GPU
AMIs. Do not assume the stock AMI contains this path. Bootstrap verifies that the
executable runs before starting ECS; it does not install packages or download a
fallback in this mode. A system Python-based CLI may depend on host libraries
that are unavailable when mounted into task containers; use a self-contained
installation compatible with the task images.

This setting refers to the **EC2 AMI**, not the workflow Docker image. Terraform
exports the selected path as `aws_cli_path`; reload the environment helper after
deploying the change. Updated bootstrap applies to newly launched instances,
not instances already running.
