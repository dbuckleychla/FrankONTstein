terraform {
  required_version = ">= 1.9.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.13.0"
    }
  }
}
provider "aws" {
  region = var.region
  default_tags { tags = merge(var.tags, { ManagedBy = "Terraform", Project = var.name }) }
}
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_availability_zones" "available" { state = "available" }
