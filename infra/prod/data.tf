data "aws_iam_role" "lab_role" {
  name = "LabRole"
}
data "aws_caller_identity" "current" {}

data "aws_eks_cluster" "cluster" {
  name = aws_eks_cluster.main.name
}


data "aws_eks_cluster_auth" "auth" {
  name = var.clusterName
}