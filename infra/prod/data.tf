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

locals {
  #---> Bucket público do JWKS criado pelo fiap-lambda (s3.tf). 
  jwt_issuer = var.jwtIssuer != "" ? var.jwtIssuer : "https://fiap-jwt-jwks-${data.aws_caller_identity.current.account_id}.s3.${var.region}.amazonaws.com"
}
