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
  default     = null
  description = "Existing work/results bucket; null creates an account/region-qualified bucket."
}
variable "read_bucket_arns" {
  type        = list(string)
  default     = []
  description = "Additional input/reference bucket ARNs readable by tasks and coordinator."
}
variable "kms_key_arn" {
  type        = string
  default     = null
  description = "Optional customer-managed key for the managed S3 bucket."
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
