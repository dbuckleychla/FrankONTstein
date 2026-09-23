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
