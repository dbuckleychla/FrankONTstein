locals {
  partition = data.aws_partition.current.partition
  keys      = distinct(concat(var.read_kms_key_arns, var.kms_key_arn == null ? [] : [var.kms_key_arn]))
}
data "aws_iam_policy_document" "task_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "task" {
  name_prefix          = "${var.name}-task-"
  assume_role_policy   = data.aws_iam_policy_document.task_trust.json
  permissions_boundary = var.permissions_boundary_arn
}
data "aws_iam_policy_document" "data" {
  statement {
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = concat([local.bucket_arn], var.read_bucket_arns)
  }
  statement {
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = [for arn in concat([local.bucket_arn], var.read_bucket_arns) : "${arn}/*"]
  }
  statement {
    actions   = ["s3:PutObject", "s3:AbortMultipartUpload", "s3:DeleteObject"]
    resources = ["${local.bucket_arn}/work/*", "${local.bucket_arn}/results/*"]
  }
  dynamic "statement" {
    for_each = length(local.keys) > 0 ? [1] : []
    content {
      actions   = ["kms:Decrypt", "kms:DescribeKey"]
      resources = local.keys
    }
  }
  dynamic "statement" {
    for_each = var.kms_key_arn == null ? [] : [var.kms_key_arn]
    content {
      actions   = ["kms:GenerateDataKey"]
      resources = [statement.value]
    }
  }
}
resource "aws_iam_policy" "data" {
  name_prefix = "${var.name}-data-"
  policy      = data.aws_iam_policy_document.data.json
}
resource "aws_iam_role_policy_attachment" "task_data" {
  role       = aws_iam_role.task.name
  policy_arn = aws_iam_policy.data.arn
}
resource "aws_iam_role" "instance" {
  name_prefix          = "${var.name}-instance-"
  permissions_boundary = var.permissions_boundary_arn
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" }
  }] })
}
resource "aws_iam_role_policy_attachment" "instance" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}
resource "aws_iam_instance_profile" "batch" { role = aws_iam_role.instance.name }
resource "aws_iam_role" "batch" {
  name_prefix          = "${var.name}-service-"
  permissions_boundary = var.permissions_boundary_arn
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "batch.amazonaws.com" }
  }] })
}
resource "aws_iam_role_policy_attachment" "batch" {
  role       = aws_iam_role.batch.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AWSBatchServiceRole"
}
resource "aws_iam_role" "spot" {
  count                = var.spot ? 1 : 0
  name_prefix          = "${var.name}-spot-"
  permissions_boundary = var.permissions_boundary_arn
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "spotfleet.amazonaws.com" }
  }] })
}
resource "aws_iam_role_policy_attachment" "spot" {
  count      = var.spot ? 1 : 0
  role       = aws_iam_role.spot[0].name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole"
}
data "aws_iam_policy_document" "coordinator" {
  source_policy_documents = [data.aws_iam_policy_document.data.json]
  statement {
    actions   = ["logs:GetLogEvents", "logs:DescribeLogStreams"]
    resources = ["${aws_cloudwatch_log_group.batch.arn}:*"]
  }
  statement {
    actions   = ["batch:SubmitJob"]
    resources = concat([aws_batch_job_queue.this.arn, "arn:${local.partition}:batch:${var.region}:${data.aws_caller_identity.current.account_id}:job-definition/nf-*"], aws_batch_job_queue.gpu[*].arn)
  }
  statement {
    actions   = ["batch:DescribeJobs", "batch:DescribeJobDefinitions", "batch:DescribeJobQueues", "batch:RegisterJobDefinition"]
    resources = ["*"]
  }
  statement {
    actions   = ["batch:TerminateJob"]
    resources = ["arn:${local.partition}:batch:${var.region}:${data.aws_caller_identity.current.account_id}:job/*"]
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.task.arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}
resource "aws_iam_policy" "coordinator" {
  name_prefix = "${var.name}-coordinator-"
  policy      = data.aws_iam_policy_document.coordinator.json
}
