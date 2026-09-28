variable "region" {
  type        = string
  description = "AWS region. Credentials use the standard AWS SDK chain."
}
variable "name" {
  type    = string
  default = "frankontstein"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}$", var.name))
    error_message = "Use 3–24 lower-case letters, digits and hyphens."
  }
}
variable "tags" {
  type    = map(string)
  default = {}
}
variable "vpc_id" {
  type        = string
  default     = null
  description = "Existing VPC; null creates a VPC with private Batch subnets and NAT."
}
variable "subnet_ids" {
  type    = list(string)
  default = []
  validation {
    condition     = (var.vpc_id == null && length(var.subnet_ids) == 0) || (var.vpc_id != null && length(var.subnet_ids) > 0)
    error_message = "Supply both vpc_id and subnet_ids, or neither."
  }
}
variable "vpc_cidr" {
  type    = string
  default = "10.82.0.0/16"
}
variable "bucket_name" {
  type        = string
  nullable    = false
  description = "Required existing S3 bucket name. Terraform never creates, deletes or configures this bucket."
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.bucket_name))
    error_message = "Supply an existing S3 bucket name, not an ARN, URL or path."
  }
}
variable "s3_prefix" {
  type        = string
  default     = "frankONTstein/"
  nullable    = false
  description = "Nonempty relative prefix containing work/ and results/; optional trailing slash."
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._/-]*/?$", var.s3_prefix)) && alltrue([for part in split("/", trimsuffix(var.s3_prefix, "/")) : !contains(["", ".", ".."], part)])
    error_message = "Use a nonempty relative S3 prefix without empty, dot or parent-directory components."
  }
}
variable "read_bucket_arns" {
  type        = list(string)
  default     = []
  description = "Additional input/reference bucket ARNs readable by tasks and coordinator."
}
variable "kms_key_arn" {
  type        = string
  default     = null
  description = "Optional existing key used by the supplied S3 bucket. Grants task/coordinator KMS access only; does not configure encryption."
}
variable "read_kms_key_arns" {
  type    = list(string)
  default = []
}
variable "permissions_boundary_arn" {
  type    = string
  default = null
}
variable "instance_types" {
  type    = list(string)
  default = ["m6i", "r6i"]
}
variable "max_vcpus" {
  type    = number
  default = 128
  validation {
    condition     = var.max_vcpus > 0
    error_message = "max_vcpus must be positive."
  }
}
variable "spot" {
  type    = bool
  default = false
}
variable "scratch_gb" {
  type    = number
  default = 500
}
variable "log_retention_days" {
  type    = number
  default = 30
}
variable "aws_cli_version" {
  type    = string
  default = "2.31.0"
  validation {
    condition     = can(regex("^2\\.[0-9]+\\.[0-9]+$", var.aws_cli_version))
    error_message = "Use an explicit AWS CLI v2 release version."
  }
}
variable "gpu_instance_types" {
  type        = list(string)
  default     = []
  description = "Optional x86-64 NVIDIA instance families, e.g. [g5]; empty disables GPU resources."
}
variable "gpu_max_vcpus" {
  type    = number
  default = 32
}

variable "use_existing_aws_cli" {
  type        = bool
  default     = false
  description = "Use AWS CLI already installed in the EC2 AMI instead of downloading it during bootstrap. Applies to CPU and GPU instances."
}
variable "existing_aws_cli_path" {
  type        = string
  default     = "/usr/local/aws-cli/v2/current/bin/aws"
  description = "Absolute path to the existing, self-contained AWS CLI installation in both EC2 AMIs; Nextflow mounts this installation into task containers."
  validation {
    condition     = can(regex("^/[A-Za-z0-9_./-]+/aws$", var.existing_aws_cli_path))
    error_message = "Use an absolute AWS CLI executable path ending in /aws, without spaces or shell metacharacters."
  }
}

variable "scratch_iops" {
  type        = number
  default     = 6000
  description = "Provisioned gp3 root-disk IOPS shared by Docker and task scratch; incurs EBS charges above baseline."
  validation {
    condition     = var.scratch_iops >= 3000 && var.scratch_iops <= 16000 && floor(var.scratch_iops) == var.scratch_iops
    error_message = "scratch_iops must be an integer from 3000 to 16000."
  }
}
variable "scratch_throughput_mibps" {
  type        = number
  default     = 500
  description = "gp3 throughput in MiB/s shared by image extraction and task I/O; limited by the EC2 instance EBS bandwidth."
  validation {
    condition     = var.scratch_throughput_mibps >= 125 && var.scratch_throughput_mibps <= 1000 && var.scratch_throughput_mibps <= var.scratch_iops / 4 && floor(var.scratch_throughput_mibps) == var.scratch_throughput_mibps
    error_message = "Use integer throughput 125–1000 MiB/s, at most one quarter of provisioned IOPS."
  }
}
