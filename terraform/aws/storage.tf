locals {
  bucket_name = var.bucket_name != null ? var.bucket_name : "${var.name}-${data.aws_caller_identity.current.account_id}-${var.region}"
  bucket_arn  = "arn:${data.aws_partition.current.partition}:s3:::${local.bucket_name}"
}
resource "aws_s3_bucket" "this" {
  count         = var.bucket_name == null ? 1 : 0
  bucket        = local.bucket_name
  force_destroy = false
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_public_access_block" "this" {
  count                   = var.bucket_name == null ? 1 : 0
  bucket                  = aws_s3_bucket.this[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "this" {
  count  = var.bucket_name == null ? 1 : 0
  bucket = aws_s3_bucket.this[0].id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  count  = var.bucket_name == null ? 1 : 0
  bucket = aws_s3_bucket.this[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.kms_key_arn == null ? "AES256" : "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}
resource "aws_s3_bucket_policy" "tls" {
  count  = var.bucket_name == null ? 1 : 0
  bucket = aws_s3_bucket.this[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Deny", Principal = "*", Action = "s3:*"
      Resource  = [local.bucket_arn, "${local.bucket_arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}
