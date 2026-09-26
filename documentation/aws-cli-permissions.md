# AWS CLI and Terraform permissions

AWS authorizes the **identity selected by your CLI profile**, not the profile
name. A profile called `superuser` does not establish its account or permissions.
This guide covers the checked-in `terraform/aws` configuration with AWS provider
6.13.0 and the Nextflow AWS Batch profile.

Use this as an administrator's action inventory, not a ready-to-attach policy.
Deployment actions below cover creation, refresh, updates and teardown; they are
not a claim of a live-tested minimum policy. Scope them to the deployment's
resources and conditions. AWS provider refresh behavior and account-specific
controls can require additional read access or service-side dependent permissions.
Runtime permissions are enumerated
from the policy documents in [iam.tf](../terraform/aws/iam.tf).

## Which identity needs which permissions?

| Identity | Responsibility |
| --- | --- |
| Terraform deployment profile | Create/read/update/delete the configured Batch, IAM, logging and optional network resources. Read the existing bucket. |
| Nextflow coordinator profile/role | Stage data, register job definitions, submit/monitor/terminate jobs, read logs and pass the task role. Attach the exported `coordinator_policy_arn` to this identity. |
| ECS task role | Read inputs/references/models and write work/results. Terraform attaches the custom data policy to this role. |
| EC2 instance, Batch service and optional Spot roles | Register workers, run containers and manage compute. Terraform attaches the corresponding AWS-managed service policies. |
| IAM administrator | Approve deployment privileges/boundaries and attach the coordinator policy. This last attachment is not performed by this Terraform configuration. |

A single profile can have deployment and coordinator permissions, but one does
not imply the other. Public GHCR image pulls do not require AWS ECR permissions
on the CLI user. Private registry authentication would be an additional setup.

## Terraform deployment permissions

The following actions belong on the **deployment identity**, subject to your
organization's resource restrictions. Delete actions are needed for teardown
and some replacements; a create-only role cannot manage the full lifecycle.

### IAM: required for the current configuration

The deployment creates two customer-managed policies (`<name>-data-*` and
`<name>-coordinator-*`), task/instance/Batch roles, an instance profile, and an
optional Spot role. The IAM policy-document data sources render JSON locally;
they do not create AWS policies themselves.

| Operation | IAM actions |
| --- | --- |
| Create/read/delete managed policies | `iam:CreatePolicy`, `iam:GetPolicy`, `iam:GetPolicyVersion`, `iam:ListPolicyVersions`, `iam:DeletePolicy` |
| Update managed policy contents | `iam:CreatePolicyVersion`, `iam:SetDefaultPolicyVersion`, `iam:DeletePolicyVersion` |
| Managed-policy tags | `iam:TagPolicy`, `iam:UntagPolicy`, `iam:ListPolicyTags` |
| Role lifecycle and trust policy | `iam:CreateRole`, `iam:GetRole`, `iam:UpdateRole`, `iam:UpdateAssumeRolePolicy`, `iam:DeleteRole` |
| Role tags | `iam:TagRole`, `iam:UntagRole`, `iam:ListRoleTags` |
| Role policy attachments and refresh | `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`, `iam:GetRolePolicy` |
| Instance-profile lifecycle | `iam:CreateInstanceProfile`, `iam:GetInstanceProfile`, `iam:DeleteInstanceProfile`, `iam:AddRoleToInstanceProfile`, `iam:RemoveRoleFromInstanceProfile`, `iam:ListInstanceProfilesForRole` |
| Instance-profile tags | `iam:TagInstanceProfile`, `iam:UntagInstanceProfile`, `iam:ListInstanceProfileTags` |
| Pass compute roles to AWS services | `iam:PassRole` on the Batch service role, EC2 instance role and optional Spot fleet role |
| If managing `permissions_boundary_arn` on roles | `iam:PutRolePermissionsBoundary`, `iam:DeleteRolePermissionsBoundary`; any required boundary condition must also permit `iam:CreateRole` with the configured boundary |

Restrict `iam:PassRole` to these roles and the applicable destination services
(`batch.amazonaws.com`, `ec2.amazonaws.com`, and `spotfleet.amazonaws.com`).
Validate `iam:PassedToService` conditions against the actual API path; the
coordinator's ECS-task restriction is a different policy described below.

Terraform attaches these existing policies; permission to attach them is
required, but permission to create them is not:

- `arn:<partition>:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role`
- `arn:<partition>:iam::aws:policy/service-role/AWSBatchServiceRole`
- When `spot = true`: `arn:<partition>:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole`

First-time account setup can also require an administrator to create AWS
service-linked roles. Where AWS requires one and it does not already exist,
`iam:CreateServiceLinkedRole` must be authorized for the relevant service name
using `iam:AWSServiceName`. ECS and EC2 Spot/Spot Fleet are relevant to this
compute path. This configuration explicitly supplies a custom Batch service
role; do not assume that all service-linked roles must be created on every run.

### AWS Batch and CloudWatch Logs: required

| Resource / operation | Actions |
| --- | --- |
| Compute environments, CPU and optional GPU | `batch:CreateComputeEnvironment`, `batch:DescribeComputeEnvironments`, `batch:UpdateComputeEnvironment`, `batch:DeleteComputeEnvironment` |
| Job queues, CPU and optional GPU | `batch:CreateJobQueue`, `batch:DescribeJobQueues`, `batch:UpdateJobQueue`, `batch:DeleteJobQueue` |
| Batch tags | `batch:TagResource`, `batch:UntagResource`, `batch:ListTagsForResource` |
| Log group | `logs:CreateLogGroup`, `logs:DescribeLogGroups`, `logs:DeleteLogGroup`, `logs:PutRetentionPolicy`, `logs:DeleteRetentionPolicy` |
| Log-group tags | `logs:TagResource`, `logs:UntagResource`, `logs:ListTagsForResource` |

If a tooling version uses the older log-group-specific tagging APIs, authorize
`logs:TagLogGroup`, `logs:UntagLogGroup` and `logs:ListTagsLogGroup` as well.

Enabling `gpu_instance_types` adds another compute environment and queue using
the same action set. CPU Spot additionally uses the Spot role above; GPU
compute remains on-demand. Instance launches and ECS operations are performed
through service/worker roles, not by copying their entire permissions onto the
Terraform user. This Terraform configuration does not submit jobs or register
job definitions; Nextflow does that at runtime.

### EC2 resources: required even with an existing VPC

| Resource / operation | Actions |
| --- | --- |
| Account/network discovery | `ec2:DescribeAvailabilityZones`, `ec2:DescribeVpcs`, `ec2:DescribeSubnets` |
| Security group | `ec2:CreateSecurityGroup`, `ec2:DescribeSecurityGroups`, `ec2:DescribeSecurityGroupRules`, `ec2:DeleteSecurityGroup` |
| Security-group rules | `ec2:AuthorizeSecurityGroupIngress`, `ec2:RevokeSecurityGroupIngress`, `ec2:AuthorizeSecurityGroupEgress`, `ec2:RevokeSecurityGroupEgress` |
| Launch template and versions | `ec2:CreateLaunchTemplate`, `ec2:DescribeLaunchTemplates`, `ec2:DescribeLaunchTemplateVersions`, `ec2:CreateLaunchTemplateVersion`, `ec2:ModifyLaunchTemplate`, `ec2:DeleteLaunchTemplateVersions`, `ec2:DeleteLaunchTemplate` |
| EC2 tags | `ec2:CreateTags`, `ec2:DeleteTags`, `ec2:DescribeTags` |

The security group has no configured ingress rules; provider reconciliation can
still use rule-revocation APIs. Launch-template version actions allow later
scratch-disk or bootstrap changes. EC2 read APIs that do not support resource
scoping require `Resource: "*"` in a policy.

### Additional EC2 permissions when Terraform creates the VPC

These apply when `vpc_id = null`. Supplying an existing VPC and subnets avoids
these resource creations, but does not remove the security-group or launch-template
requirements above.

| Resource / operation | Actions |
| --- | --- |
| VPC and DNS attributes | `ec2:CreateVpc`, `ec2:DescribeVpcAttribute`, `ec2:ModifyVpcAttribute`, `ec2:DeleteVpc` |
| Public/private subnets | `ec2:CreateSubnet`, `ec2:ModifySubnetAttribute`, `ec2:DeleteSubnet` |
| Internet gateway | `ec2:CreateInternetGateway`, `ec2:DescribeInternetGateways`, `ec2:AttachInternetGateway`, `ec2:DetachInternetGateway`, `ec2:DeleteInternetGateway` |
| Elastic IP | `ec2:AllocateAddress`, `ec2:DescribeAddresses`, `ec2:ReleaseAddress` |
| NAT gateway | `ec2:CreateNatGateway`, `ec2:DescribeNatGateways`, `ec2:DeleteNatGateway` |
| Route tables | `ec2:CreateRouteTable`, `ec2:DescribeRouteTables`, `ec2:DeleteRouteTable` |
| Routes | `ec2:CreateRoute`, `ec2:ReplaceRoute`, `ec2:DeleteRoute` |
| Route-table associations | `ec2:AssociateRouteTable`, `ec2:ReplaceRouteTableAssociation`, `ec2:DisassociateRouteTable` |
| S3 gateway endpoint | `ec2:CreateVpcEndpoint`, `ec2:DescribeVpcEndpoints`, `ec2:DescribeVpcEndpointServices`, `ec2:ModifyVpcEndpoint`, `ec2:DeleteVpcEndpoints` |
| Network dependency discovery during refresh/deletion | `ec2:DescribeNetworkInterfaces` |

EC2 tag actions from the previous table also apply to these resources.

### Existing bucket and Terraform state

For the configured existing bucket lookup, allow `s3:ListBucket` (including the
HeadBucket authorization check) and `s3:GetBucketLocation` on its bucket ARN.
Terraform does not need object-write permissions to provision this stack. It
does not create, delete or configure the bucket; bucket-owner permissions are
separate from the workload's object permissions.

There is **no remote Terraform backend declared** in this repo. If you configure
one, add the backend's permissions separately:

| Optional backend feature | Actions and scope |
| --- | --- |
| S3 state | `s3:ListBucket` on the state bucket with the appropriate prefix condition; `s3:GetObject` and `s3:PutObject` on the specific state key |
| S3 lockfile (`use_lockfile`) | `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on the corresponding `.tflock` key |
| Existing DynamoDB locking table | `dynamodb:DescribeTable`, `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:DeleteItem` on that table |
| Customer-KMS-encrypted state | `kms:Decrypt`, `kms:Encrypt`, `kms:GenerateDataKey` on the state key as needed by the backend and its key policy |

These are not permissions to create a backend bucket, table or encryption key.
Backend credentials can differ from provider credentials; check both before
changing profiles for an existing state.

## Nextflow coordinator and task permissions

These tables describe the policies actually generated by
[the Terraform IAM configuration](../terraform/aws/iam.tf), not deployment
permissions. The data policy is attached to the task role and included in the
coordinator policy.

| Data action | Resource scope in the generated policy |
| --- | --- |
| `s3:ListBucket`, `s3:GetBucketLocation` | Configured existing bucket and additional `read_bucket_arns` |
| `s3:GetObject`, `s3:GetObjectVersion` | All objects in those buckets |
| `s3:PutObject`, `s3:AbortMultipartUpload`, `s3:DeleteObject` | Only `<bucket>/<s3_prefix>/work/*` and `<bucket>/<s3_prefix>/results/*` |
| `kms:Decrypt`, `kms:DescribeKey` | Configured `kms_key_arn` and `read_kms_key_arns`, when supplied |
| `kms:GenerateDataKey` | Configured output-bucket `kms_key_arn`, when supplied |

Bucket and KMS key policies must also permit access, especially across accounts.
These grants do not change bucket encryption or key policies. No S3 bucket
delete or bucket-configuration permission is granted. S3 multipart creation,
part upload and completion use `s3:PutObject`; the configuration also grants
abort. Tools that separately enumerate multipart uploads/parts would additionally
need `s3:ListBucketMultipartUploads` / `s3:ListMultipartUploadParts`; those are not
currently granted by this Terraform policy.

The coordinator additionally receives:

| Runtime action | Resource scope in the generated policy |
| --- | --- |
| `batch:SubmitJob` | This deployment's CPU/GPU queues and `job-definition/nf-*` in the configured account and region |
| `batch:DescribeJobs`, `batch:DescribeJobDefinitions`, `batch:DescribeJobQueues`, `batch:RegisterJobDefinition` | `*` in the current policy |
| `batch:TerminateJob` | Batch jobs in the configured account and region |
| `logs:GetLogEvents`, `logs:DescribeLogStreams` | Streams in the configured Batch log group |
| `iam:PassRole` | Only the generated task role, with `iam:PassedToService = ecs-tasks.amazonaws.com` |

Job-definition registration is deliberately listed as the current `*` grant,
not a claimed least-privilege restriction. The task data policy does not grant
Batch submission or IAM management. The EC2 instance role's AWS-managed ECS
policy supplies container-instance/logging permissions; the coordinator only
reads logs.

An administrator attaching `coordinator_policy_arn` needs `iam:AttachRolePolicy`
on the chosen coordinator role, or `iam:AttachUserPolicy` on the chosen user.
Use `iam:ListAttachedRolePolicies` / `iam:ListAttachedUserPolicies` to inspect
attachments, and the matching detach actions to remove them. Terraform does not
attach this policy to an arbitrary CLI identity.

## Resource scoping for an administrator

Replace these placeholders with reviewed deployment values; these are ARN
patterns, not a complete IAM policy:

| Resource | Typical scope |
| --- | --- |
| Custom IAM policies | `arn:<partition>:iam::<account>:policy/<name>-data-*` and `...:policy/<name>-coordinator-*` |
| Generated IAM roles | `...:role/<name>-task-*`, `...:role/<name>-instance-*`, `...:role/<name>-service-*`, optional `...:role/<name>-spot-*` |
| Instance profile | Use its actual exported/state ARN; the resource currently has no explicit project name prefix |
| Batch compute environments | `arn:<partition>:batch:<region>:<account>:compute-environment/<name>-*` |
| Batch queues | `arn:<partition>:batch:<region>:<account>:job-queue/<name>` and `...:job-queue/<name>-gpu` |
| Logs | `arn:<partition>:logs:<region>:<account>:log-group:/<name>/batch` and stream ARNs where applicable |
| Network / launch template | Supported EC2 resource ARNs and request/resource tag conditions for `Project=<name>` and `ManagedBy=Terraform` |
| Existing storage | The specific bucket, configured object prefixes and KMS key ARNs |

The instance-profile name is provider-generated, unlike the explicitly prefixed
roles. Do not assume it matches `<name>-*`. Creation and describe actions vary
in their support for resource-level permissions and tag conditions; split policy
statements accordingly rather than applying one ARN or tag condition to every
action. Attaching AWS-managed policies also requires permitting those policy
ARNs in any `iam:PolicyARN` condition.

## Check a profile without creating resources

Select the intended profile explicitly, for example:

```bash
aws sts get-caller-identity --profile YOUR_DEPLOYMENT_PROFILE
AWS_PROFILE=YOUR_DEPLOYMENT_PROFILE terraform -chdir=terraform/aws plan
```

The account must match the account of the existing deployment/state before you
continue a partial apply. `sts:GetCallerIdentity` does not require an explicit
Allow grant. Role-based profiles may separately require `sts:AssumeRole` on the
target role plus a matching trust policy; SSO profiles require their normal login.
A successful plan establishes neither `iam:CreatePolicy` nor other write access.
Keep the state from a partial apply; resources successfully created before an
error should already be tracked.

To inspect the specific denied policy-creation action, substitute the target
account and the **IAM user/role ARN** (not an STS assumed-role session ARN):

```bash
aws iam simulate-principal-policy \
  --profile YOUR_DEPLOYMENT_PROFILE \
  --policy-source-arn 'arn:aws:iam::<account>:role/<deployment-role>' \
  --action-names iam:CreatePolicy \
  --resource-arns \
    'arn:aws:iam::<account>:policy/<name>-data-permission-check' \
    'arn:aws:iam::<account>:policy/<name>-coordinator-permission-check' \
  --query 'EvaluationResults[].{Action:EvalActionName,Resource:EvalResourceName,Decision:EvalDecision,MissingContext:MissingContextValues}' \
  --output json
```

This diagnostic requires `iam:SimulatePrincipalPolicy`. Optional policy-context
inspection uses `iam:GetContextKeysForPrincipalPolicy`; resolving a role ARN
can use `iam:GetRole`. These diagnostic permissions are not required merely to
run Terraform or Nextflow. Repeat simulations for the action/resource groups
above, supplying required tag, boundary or passed-service context. Do not apply
all actions to the example policy ARN: Batch, EC2, S3, IAM roles and unscoped read
actions have different resource requirements.

`allowed` is simulation evidence, not proof that a live write will succeed.
`explicitDeny` identifies a blocking deny; `implicitDeny` indicates no effective
allow for the simulated request. Inspect missing context before interpreting a
result. Simulator coverage does not fully establish effective session, resource
policy and organization/SCP restrictions. Have the account administrator verify
those controls before approving deployment; a real apply changes infrastructure
and should not be used merely as a permissions probe.

## The `iam:CreatePolicy` failure

The reported failure explicitly denied creation of the data and coordinator
policies. An additional Allow does not override that deny. Setting this repo's
`permissions_boundary_arn` changes the boundary requested for generated roles;
it does not remove a deny on the identity running Terraform.

Use an authorized deployment identity in the same account, or have an
administrator create approved policies and adapt Terraform to reference them.
The latter is not implemented by the current configuration. Neighboring ONT/MSQ
repos attach existing AWS-managed policies, including `AmazonS3FullAccess`,
which avoids these custom-policy creations but broadens data access and does
not replace this coordinator policy. Do not switch to that pattern solely to
circumvent a denied IAM operation.
