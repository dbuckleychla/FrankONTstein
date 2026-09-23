# Offline plans: mocked AWS provider; no AWS credentials or deployments.
mock_provider "aws" {
  mock_data "aws_s3_bucket" {
    defaults = {
      id  = "existing-test-bucket"
      arn = "arn:aws:s3:::existing-test-bucket"
    }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-1a", "us-east-1b"] }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{}" }
  }
}
variables {
  region      = "us-east-1"
  bucket_name = "existing-test-bucket"
}
run "default_prefix" {
  command = plan
  assert {
    condition     = output.work_dir == "s3://existing-test-bucket/frankONTstein/work"
    error_message = "Work must use the required existing bucket and case-sensitive default prefix."
  }
  assert {
    condition     = output.nextflow_params.outdir == "s3://existing-test-bucket/frankONTstein/results"
    error_message = "Results must use the same default prefix."
  }
}
run "custom_prefix" {
  command = plan
  variables { s3_prefix = "team/run-1/" }
  assert {
    condition     = output.work_dir == "s3://existing-test-bucket/team/run-1/work"
    error_message = "Normalize trailing slash without duplicating separators."
  }
  assert {
    condition     = output.nextflow_params.outdir == "s3://existing-test-bucket/team/run-1/results"
    error_message = "Custom prefix must apply to results too."
  }
}
run "reject_root_prefix" {
  command = plan
  variables { s3_prefix = "/" }
  expect_failures = [var.s3_prefix]
}
run "reject_parent_prefix" {
  command = plan
  variables { s3_prefix = "team/../other" }
  expect_failures = [var.s3_prefix]
}
run "reject_bucket_url" {
  command = plan
  variables { bucket_name = "s3://existing-test-bucket" }
  expect_failures = [var.bucket_name]
}
