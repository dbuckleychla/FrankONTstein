resource "aws_launch_template" "batch" {
  name_prefix = "${var.name}-"
  user_data   = base64encode(templatefile("${path.module}/templates/user_data.mime", { aws_cli_version = var.aws_cli_version, use_existing_aws_cli = var.use_existing_aws_cli, existing_aws_cli_path = var.existing_aws_cli_path }))
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = var.scratch_gb
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }
}
resource "aws_batch_compute_environment" "this" {
  name_prefix  = "${var.name}-"
  type         = "MANAGED"
  service_role = aws_iam_role.batch.arn
  compute_resources {
    type                = var.spot ? "SPOT" : "EC2"
    allocation_strategy = var.spot ? "SPOT_PRICE_CAPACITY_OPTIMIZED" : "BEST_FIT_PROGRESSIVE"
    min_vcpus           = 0
    max_vcpus           = var.max_vcpus
    instance_type       = var.instance_types
    instance_role       = aws_iam_instance_profile.batch.arn
    spot_iam_fleet_role = var.spot ? aws_iam_role.spot[0].arn : null
    subnets             = local.subnets
    security_group_ids  = [aws_security_group.batch.id]
    ec2_configuration { image_type = "ECS_AL2023" }
    launch_template {
      launch_template_id = aws_launch_template.batch.id
      version            = tostring(aws_launch_template.batch.latest_version)
    }
  }
  depends_on = [aws_iam_role_policy_attachment.batch, aws_iam_role_policy_attachment.instance, aws_iam_role_policy_attachment.spot]
  lifecycle { create_before_destroy = true }
}
resource "aws_batch_job_queue" "this" {
  name     = var.name
  state    = "ENABLED"
  priority = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.this.arn
  }
}
resource "aws_cloudwatch_log_group" "batch" {
  name              = "/${var.name}/batch"
  retention_in_days = var.log_retention_days
}
resource "aws_batch_compute_environment" "gpu" {
  count        = length(var.gpu_instance_types) > 0 ? 1 : 0
  name_prefix  = "${var.name}-gpu-"
  type         = "MANAGED"
  service_role = aws_iam_role.batch.arn
  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT_PROGRESSIVE"
    min_vcpus           = 0
    max_vcpus           = var.gpu_max_vcpus
    instance_type       = var.gpu_instance_types
    instance_role       = aws_iam_instance_profile.batch.arn
    subnets             = local.subnets
    security_group_ids  = [aws_security_group.batch.id]
    ec2_configuration { image_type = "ECS_AL2023_NVIDIA" }
    launch_template {
      launch_template_id = aws_launch_template.batch.id
      version            = tostring(aws_launch_template.batch.latest_version)
    }
  }
  depends_on = [aws_iam_role_policy_attachment.batch, aws_iam_role_policy_attachment.instance]
  lifecycle { create_before_destroy = true }
}
resource "aws_batch_job_queue" "gpu" {
  count    = length(var.gpu_instance_types) > 0 ? 1 : 0
  name     = "${var.name}-gpu"
  state    = "ENABLED"
  priority = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.gpu[0].arn
  }
}
