
resource "aws_cloudwatch_log_group" "eks_control_plane" {
  name              = "/aws/eks/${var.clusterName}/cluster"
  retention_in_days = var.logRetentionDays
}

resource "aws_cloudwatch_log_group" "container_insights" {
  for_each = toset(["application", "dataplane", "host", "performance"])

  name              = "/aws/containerinsights/${var.clusterName}/${each.value}"
  retention_in_days = var.logRetentionDays
}
