locals {
  # Aponta exatamente para a Role de federacao/console do AWS Academy
  voclabs_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/voclabs"
}

resource "aws_eks_access_entry" "access_entry_lab" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = data.aws_iam_role.lab_role.arn
  type          = "EC2_LINUX"
}


resource "aws_eks_access_entry" "access_entry_console" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = local.voclabs_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "eks_policy_console" {
  cluster_name  = aws_eks_cluster.main.name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  principal_arn = local.voclabs_role_arn

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.access_entry_console]
}