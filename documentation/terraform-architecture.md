# AWS Terraform architecture

The configuration in [`terraform/aws`](../terraform/aws/) provisions AWS Batch
workers and supporting infrastructure. Nextflow runs on a **user-managed,
persistent coordinator host**; Terraform does not create that host. Solid arrows
show job or data flow; dotted arrows show configuration and permissions.

```mermaid
flowchart TB
    TF["Terraform<br/>terraform/aws"]
    OUTPUTS["Outputs<br/>Region, queues, task role, log group, S3 paths"]
    COORD["User-managed coordinator<br/>Nextflow with AWS profile<br/>Persistent .nextflow/cache and launch directory"]
    POLICY["Coordinator IAM policy<br/>Attach to coordinator identity"]
    CPUQ["AWS Batch CPU queue"]
    GPUQ["Optional AWS Batch GPU queue"]

    subgraph VPC["New VPC or existing VPC and supplied subnets"]
        subgraph PRIVATE["Compute subnets<br/>New VPC: two private subnets across two AZs"]
            CPU["Managed CPU compute environment<br/>On-demand default; optional Spot<br/>Minimum 0 vCPUs"]
            GPU["Optional managed GPU compute environment<br/>On-demand; minimum 0 vCPUs"]
            TASKS["EC2 / ECS task containers<br/>Digest-pinned analysis images<br/>No inbound security-group rules"]
            DISK["Encrypted gp3 scratch volume per worker<br/>Deleted when instance terminates"]
        end
        subgraph PUBLIC["New VPC: one public subnet"]
            NAT["Single NAT gateway + Elastic IP"]
        end
        IGW["Internet gateway"]
        S3EP["S3 gateway endpoint<br/>New VPC only"]
    end

    REG["Public OCI registries<br/>GHCR and other configured image sources"]
    S3["Required existing S3 bucket<br/>frankONTstein/work/ and frankONTstein/results/"]
    READ["Optional additional read-only S3 buckets<br/>Inputs and reference assets"]
    LOGS["CloudWatch Logs<br/>Configured retention"]
    ROLE["Task IAM role<br/>Read configured buckets<br/>Write configured work/results prefixes"]
    KMS["Optional existing KMS keys"]
    INFRAIAM["Batch service role + EC2 instance profile<br/>Optional Spot fleet role"]

    TF -.-> OUTPUTS
    TF -.-> POLICY
    TF -.-> INFRAIAM
    OUTPUTS -.-> COORD
    POLICY -.-> COORD
    COORD -->|Submit and monitor jobs| CPUQ
    COORD -->|GPU jobs when enabled| GPUQ
    CPUQ --> CPU
    GPUQ --> GPU
    CPU --> TASKS
    GPU --> TASKS
    INFRAIAM -.-> CPU
    INFRAIAM -.-> GPU
    ROLE -.-> TASKS
    TASKS <--> DISK
    TASKS -->|Image pulls and public services| NAT
    NAT --> IGW
    IGW --> REG
    TASKS <-->|Stage inputs and task outputs| S3EP
    S3EP <--> S3
    S3EP --> READ
    COORD <--> S3
    COORD --> READ
    TASKS --> LOGS
    COORD -->|Read task logs| LOGS
    KMS -.-> ROLE
```

## Networking and storage choices

- **New VPC:** Terraform creates two private compute subnets, a public subnet,
  one NAT gateway, an internet gateway, routing and an S3 gateway endpoint.
  Private workers use the NAT for public image pulls and other public services;
  regional S3 traffic uses the gateway endpoint.
- **Existing VPC:** supply `vpc_id` and `subnet_ids`. Terraform creates the Batch
  security group but does not create NAT, routes or endpoints. The supplied
  network must provide outbound access to registries and required AWS services.
- **Existing bucket required:** Terraform only looks it up; it never creates,
  deletes or changes bucket settings. Encryption, policies, versioning, lifecycle
  and retention stay with the bucket owner. The default `s3_prefix` is
  `frankONTstein/`; writes/cleanup are limited to its `work/` and `results/`
  paths. Additional input buckets can be granted read access.
- **Upgrades:** migration blocks forget old managed bucket/settings resources
  without changing AWS. Apply the reviewed migration before teardown; see the
  [AWS guide](../docs/aws.md#upgrading-an-existing-terraform-state).

The GPU queue exists only when `gpu_instance_types` is configured. CPU Spot is
optional; the GPU environment remains on-demand. Both environments can scale to
zero, but NAT gateway, storage, logs and any coordinator host still incur costs.
The new VPC uses a single NAT gateway, so outbound connectivity depends on that
availability zone and traffic from the other zone can incur cross-AZ charges.

See [AWS CLI and Terraform permissions](aws-cli-permissions.md) for the deployment
action inventory, runtime policy scopes, and profile-check commands.

## Coordinator and resume

Attach the exported `coordinator_policy_arn` to the coordinator's IAM identity.
The [AWS environment helper](aws-batch-launch.md) reads `nextflow_params` and
`work_dir`, adds a run-specific path suffix and exports defaults consumed by the
Nextflow AWS profile. Run Nextflow directly after loading the exports. Nextflow registers task job definitions and submits them to Batch;
Terraform provisions the compute environments and queues.

Preserve the coordinator's launch directory and `.nextflow/cache` together with
the S3 work prefix to support `-resume`. Worker scratch disks are disposable and
are not the persistent Nextflow cache. Terraform state must also be retained
separately by the operator.

See the [AWS setup guide](../docs/aws.md) and
[run examples](run-examples.md) for commands. This diagram describes the checked-in
configuration; it does not establish that a live AWS smoke run has passed.
