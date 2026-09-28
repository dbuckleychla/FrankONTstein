resource "aws_cloudwatch_log_group" "hosts" {
  name              = "/${var.name}/hosts"
  retention_in_days = var.log_retention_days
}

# Worker permissions only: task containers do not need access to host diagnostics.
resource "aws_iam_role_policy" "host_diagnostics" {
  name = "${var.name}-host-diagnostics"
  role = aws_iam_role.instance.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = [aws_cloudwatch_log_group.hosts.arn, "${aws_cloudwatch_log_group.hosts.arn}:*"]
      },
      {
        Effect    = "Allow"
        Action    = ["cloudwatch:PutMetricData"]
        Resource  = "*"
        Condition = { StringEquals = { "cloudwatch:namespace" = "FrankONTstein/BatchHost" } }
      }
    ]
  })
}

locals {
  host_agent_config = jsonencode({
    agent = { region = var.region, metrics_collection_interval = 60, run_as_user = "root" }
    logs = {
      force_flush_interval = 5
      logs_collected = { files = { collect_list = [
        for entry in [
          { path = "/var/log/frankontstein/host-journal.log", stream = "journal" },
          { path = "/var/log/ecs/ecs-agent.log*", stream = "ecs-agent" },
          { path = "/var/log/cloud-init-output.log", stream = "bootstrap" },
          { path = "/opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log", stream = "logging-agent" }
          ] : {
          file_path       = entry.path
          log_group_name  = aws_cloudwatch_log_group.hosts.name
          log_stream_name = "{instance_id}/${entry.stream}"
          timezone        = "UTC"
        }
      ] } }
    }
    metrics = {
      namespace         = "FrankONTstein/BatchHost"
      append_dimensions = { InstanceId = "$${aws:InstanceId}" }
      metrics_collected = {
        mem    = { measurement = ["mem_used_percent", "mem_available"] }
        swap   = { measurement = ["swap_used_percent"] }
        disk   = { resources = ["/"], measurement = ["used_percent", "inodes_free"] }
        diskio = { resources = ["*"], measurement = ["io_time", "iops_in_progress", "read_bytes", "write_bytes", "read_time", "write_time"] }
      }
    }
  })
}

output "host_diagnostics" {
  value = {
    log_group        = aws_cloudwatch_log_group.hosts.name
    metric_namespace = "FrankONTstein/BatchHost"
    note             = "New workers only after deployment; no SSH or SSM required."
  }
}
