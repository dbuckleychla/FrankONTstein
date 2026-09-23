# Read-only lookup: storage is always supplied and managed by the bucket owner.
data "aws_s3_bucket" "existing" {
  bucket = var.bucket_name
}

locals {
  bucket_name    = data.aws_s3_bucket.existing.id
  bucket_arn     = data.aws_s3_bucket.existing.arn
  s3_prefix      = trimsuffix(var.s3_prefix, "/")
  work_prefix    = "${local.s3_prefix}/work"
  results_prefix = "${local.s3_prefix}/results"
}

# Upgrade safety: forget buckets/settings managed by older releases without
# deleting the bucket or changing any of its settings. Keep these migration blocks.
removed {
  from = aws_s3_bucket.this
  lifecycle { destroy = false }
}
removed {
  from = aws_s3_bucket_public_access_block.this
  lifecycle { destroy = false }
}
removed {
  from = aws_s3_bucket_versioning.this
  lifecycle { destroy = false }
}
removed {
  from = aws_s3_bucket_server_side_encryption_configuration.this
  lifecycle { destroy = false }
}
removed {
  from = aws_s3_bucket_policy.tls
  lifecycle { destroy = false }
}
