resource "aws_eks_cluster" "main" {
  name     = var.clusterName
  role_arn = data.aws_iam_role.lab_role.arn

  enabled_cluster_log_types = var.clusterLogTypes

  encryption_config {
    resources = ["secrets"]
    provider { key_arn = aws_kms_key.eks_secrets.arn }
  }

  vpc_config {
    subnet_ids              = [aws_subnet.public.id, aws_subnet.private.id]
    security_group_ids      = [aws_security_group.sg.id]
    endpoint_private_access = true
    endpoint_public_access  = false
  }

  access_config {
    authentication_mode = var.accessConfig
  }


  depends_on = [
    data.aws_iam_role.lab_role,
    aws_cloudwatch_log_group.eks_control_plane
  ]
}

resource "aws_kms_key" "eks_secrets" {
  description         = "Encryption of legacy EKS Kubernetes secrets"
  enable_key_rotation = true
}
resource "aws_eks_addon" "metrics_server" {
  cluster_name                = aws_eks_cluster.main.name
  addon_name                  = "metrics-server"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  timeouts {
    create = "10m"
    update = "10m"
  }

  depends_on = [
    aws_eks_cluster.main,
    aws_eks_node_group.main
  ]
}
